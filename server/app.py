"""PixelPeak API — регистрация, вход и сессии аккаунтов.

Запуск:
    uvicorn app:app --host 0.0.0.0 --port 8000
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import os
import re
import time
from typing import Optional

from fastapi import FastAPI, HTTPException, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, field_validator

import database as db
import security as sec

SESSION_TTL = 60 * 60 * 24 * 30  # 30 дней
ADMIN_KEY_TTL = 60 * 60 * 12  # 12 часов
ADMIN_PASSWORD_HASH = os.environ.get(
    "PIXELPEAK_ADMIN_PASSWORD_HASH",
    "42e75ca549bd97318b9bc1d046854394f03aecf3f97bd3ece7ed3458214171fd",
)
_admin_keys: dict[str, float] = {}

USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{3,16}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

app = FastAPI(title="PixelPeak API", version="1.0.0")

db.init_db()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup() -> None:
    db.init_db()


# --- схемы ------------------------------------------------------------------

class RegisterPayload(BaseModel):
    username: str
    email: str
    password: str

    @field_validator("username")
    @classmethod
    def _username(cls, v: str) -> str:
        v = v.strip()
        if not USERNAME_RE.match(v):
            raise ValueError("Ник: 3-16 символов, только A-Z, a-z, 0-9 и _")
        return v

    @field_validator("email")
    @classmethod
    def _email(cls, v: str) -> str:
        v = v.strip().lower()
        if not EMAIL_RE.match(v):
            raise ValueError("Некорректный email")
        return v

    @field_validator("password")
    @classmethod
    def _password(cls, v: str) -> str:
        if len(v) < 6:
            raise ValueError("Пароль минимум 6 символов")
        return v


class LoginPayload(BaseModel):
    username: str
    password: str


class ImagePayload(BaseModel):
    image: str


class GroupCreatePayload(BaseModel):
    name: str = ""
    members: list[str] = []


class AddMemberPayload(BaseModel):
    username: str


DATAURL_RE = re.compile(r"^data:image/(png|jpeg|jpg|webp);base64,([A-Za-z0-9+/=]+)$", re.I)
PNG_SIG = b"\x89PNG\r\n\x1a\n"


def parse_image(data_url: str, *, is_skin: bool) -> tuple[str, str]:
    m = DATAURL_RE.match(data_url or "")
    if not m:
        raise HTTPException(status_code=422, detail="Неверный формат изображения")
    fmt = m.group(1).lower()
    if fmt == "jpg":
        fmt = "jpeg"
    try:
        raw = base64.b64decode(m.group(2), validate=True)
    except (binascii.Error, ValueError):
        raise HTTPException(status_code=422, detail="Не удалось прочитать изображение")
    max_size = 64 * 1024 if is_skin else 512 * 1024
    if len(raw) > max_size:
        raise HTTPException(status_code=413, detail="Файл слишком большой")
    if is_skin:
        if not raw.startswith(PNG_SIG) or len(raw) < 24:
            raise HTTPException(status_code=422, detail="Скин должен быть PNG")
        w = int.from_bytes(raw[16:20], "big")
        h = int.from_bytes(raw[20:24], "big")
        if not (w == 64 and h in (64, 32)):
            raise HTTPException(status_code=422, detail="Скин должен быть 64×64 или 64×32")
    return m.group(2), "image/" + fmt


def _public_group_members(group: dict) -> list[dict]:
    result = []
    for uid in group["members"]:
        u = db.get_user_by_id(uid)
        if not u:
            continue
        has_avatar = db.has_media(uid, "avatar")
        has_skin = db.has_media(uid, "skin")
        result.append(
            {
                "username": u["username"],
                "uuid": u["uuid"],
                "owner": uid == group["owner_id"],
                "has_avatar": has_avatar,
                "avatar_url": f"/api/avatar/{u['uuid']}" if has_avatar else None,
                "has_skin": has_skin,
                "skin_url": f"/api/skin/{u['uuid']}" if has_skin else None,
            }
        )
    return result


def public_user(user: dict) -> dict:
    return {
        "id": user["id"],
        "username": user["username"],
        "email": user["email"],
        "uuid": user["uuid"],
        "is_admin": bool(user["is_admin"]),
        "created_at": user["created_at"],
        "has_avatar": db.has_media(user["id"], "avatar"),
        "has_skin": db.has_media(user["id"], "skin"),
    }


def _bearer(authorization: Optional[str]) -> Optional[str]:
    if not authorization:
        return None
    if authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return authorization.strip()


def current_user(authorization: Optional[str]) -> dict:
    token = _bearer(authorization)
    if not token:
        raise HTTPException(status_code=401, detail="Нет токена авторизации")
    session = db.get_session(token)
    if not session:
        raise HTTPException(status_code=401, detail="Сессия недействительна или истекла")
    user = db.get_user_by_id(session["user_id"])
    if not user:
        raise HTTPException(status_code=401, detail="Пользователь не найден")
    return user


def require_admin(authorization: Optional[str], admin_key: Optional[str]) -> dict:
    user = current_user(authorization)
    if not user["is_admin"]:
        raise HTTPException(status_code=403, detail="Нет доступа")
    key = (admin_key or "").strip()
    if not key:
        raise HTTPException(status_code=401, detail="Введите пароль админ-панели")
    ts = _admin_keys.get(key)
    if ts is None or ts < time.time():
        _admin_keys.pop(key, None)
        raise HTTPException(status_code=401, detail="Пароль неверный или истёк")
    return user


# --- эндпоинты --------------------------------------------------------------

@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "service": "PixelPeak", "time": int(time.time())}


@app.post("/api/register")
def register(payload: RegisterPayload) -> JSONResponse:
    if db.get_user_by_username(payload.username):
        raise HTTPException(status_code=409, detail="Такой ник уже занят")
    if db.get_user_by_email(payload.email):
        raise HTTPException(status_code=409, detail="Email уже зарегистрирован")

    user = db.create_user(payload.username, payload.email, sec.hash_password(payload.password))

    token = sec.new_token()
    db.create_session(user["id"], token, SESSION_TTL)
    db.touch_login(user["id"])
    return JSONResponse(
        {"token": token, "user": public_user(user)}, status_code=201
    )


@app.post("/api/login")
def login(payload: LoginPayload) -> dict:
    user = db.get_user_by_username(payload.username)
    if user is None:
        user = db.get_user_by_email(payload.username)
    if user is None or not sec.verify_password(payload.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Неверный ник или пароль")

    token = sec.new_token()
    db.create_session(user["id"], token, SESSION_TTL)
    db.touch_login(user["id"])
    return {"token": token, "user": public_user(user)}


@app.get("/api/user_exists")
def user_exists(username: str = "") -> dict:
    name = username.strip()
    u = db.get_user_by_username(name) if name else None
    return {"exists": u is not None, "username": name}


@app.post("/api/logout")
def logout(authorization: Optional[str] = Header(default=None)) -> dict:
    token = _bearer(authorization)
    if token:
        db.delete_session(token)
    return {"ok": True}


@app.get("/api/me")
def me(authorization: Optional[str] = Header(default=None)) -> dict:
    return public_user(current_user(authorization))


# --- профиль: аватар и скин -------------------------------------------------

@app.post("/api/profile/avatar")
def upload_avatar(payload: ImagePayload, authorization: Optional[str] = Header(default=None)) -> dict:
    user = current_user(authorization)
    data, mtype = parse_image(payload.image, is_skin=False)
    db.set_media(user["id"], "avatar", data, mtype)
    return {"ok": True, "url": f"/api/avatar/{user['uuid']}"}


@app.post("/api/profile/skin")
def upload_skin(payload: ImagePayload, authorization: Optional[str] = Header(default=None)) -> dict:
    user = current_user(authorization)
    data, mtype = parse_image(payload.image, is_skin=True)
    db.set_media(user["id"], "skin", data, mtype)
    return {"ok": True, "url": f"/api/skin/{user['uuid']}"}


@app.get("/api/avatar/{user_uuid}")
def get_avatar(user_uuid: str):
    u = db.get_user_by_uuid(user_uuid)
    rec = db.get_media(u["id"], "avatar") if u else None
    if not rec:
        raise HTTPException(status_code=404, detail="Not found")
    return Response(
        content=base64.b64decode(rec["data"]),
        media_type=rec["type"],
        headers={"Cache-Control": "public, max-age=120"},
    )


@app.get("/api/skin/{user_uuid}")
def get_skin(user_uuid: str):
    u = db.get_user_by_uuid(user_uuid)
    rec = db.get_media(u["id"], "skin") if u else None
    if not rec:
        raise HTTPException(status_code=404, detail="Not found")
    return Response(
        content=base64.b64decode(rec["data"]),
        media_type=rec["type"],
        headers={"Cache-Control": "public, max-age=120"},
    )


@app.get("/api/user/{user_uuid}")
def user_profile(user_uuid: str) -> dict:
    u = db.get_user_by_uuid(user_uuid)
    if not u:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    has_avatar = db.has_media(u["id"], "avatar")
    has_skin = db.has_media(u["id"], "skin")
    return {
        "username": u["username"],
        "uuid": u["uuid"],
        "created_at": u["created_at"],
        "has_avatar": has_avatar,
        "avatar_url": f"/api/avatar/{u['uuid']}" if has_avatar else None,
        "has_skin": has_skin,
        "skin_url": f"/api/skin/{u['uuid']}" if has_skin else None,
    }


# --- CustomSkinLoader (скины в игре) ---------------------------------------

_csl_hashes: dict[str, int] = {}


@app.get("/api/csl/{username}.json")
def csl_profile(username: str) -> JSONResponse:
    u = db.get_user_by_username(username)
    rec = db.get_media(u["id"], "skin") if u else None
    if not rec:
        raise HTTPException(status_code=404, detail="Not found")
    digest = hashlib.sha256(base64.b64decode(rec["data"])).hexdigest()
    _csl_hashes[digest] = u["id"]
    return JSONResponse(
        {"username": u["username"], "skin": digest, "textures": {"default": digest}},
        headers={"Cache-Control": "public, max-age=120"},
    )


@app.get("/api/csl/textures/{digest}")
def csl_texture(digest: str):
    user_id = _csl_hashes.get(digest.lower())
    rec = db.get_media(user_id, "skin") if user_id is not None else None
    if not rec:
        raise HTTPException(status_code=404, detail="Not found")
    return Response(
        content=base64.b64decode(rec["data"]),
        media_type=rec["type"],
        headers={"Cache-Control": "public, max-age=120"},
    )


# --- группы -----------------------------------------------------------------

@app.get("/api/groups")
def list_groups(authorization: Optional[str] = Header(default=None)) -> dict:
    user = current_user(authorization)
    groups = [
        {
            "id": g["id"],
            "name": g["name"],
            "owner": g["owner_id"] == user["id"],
            "member_count": g["member_count"],
            "created_at": g["created_at"],
        }
        for g in db.list_groups_for_user(user["id"])
    ]
    return {"groups": groups}


@app.post("/api/groups")
def create_group(payload: GroupCreatePayload, authorization: Optional[str] = Header(default=None)) -> JSONResponse:
    user = current_user(authorization)
    name = payload.name.strip()[:40] or "Моя группа"
    member_ids = [user["id"]]
    not_found = []
    for uname in payload.members[:20]:
        clean = str(uname or "").strip()
        if not clean:
            continue
        other = db.get_user_by_username(clean)
        if other and other["id"] not in member_ids:
            member_ids.append(other["id"])
        elif not other:
            not_found.append(clean)
    group = db.create_group(name, user["id"], member_ids)
    return JSONResponse(
        {
            "group": {"id": group["id"], "name": group["name"], "member_count": len(group["members"]), "owner": True},
            "not_found": not_found,
        },
        status_code=201,
    )


@app.get("/api/groups/{group_id}")
def get_group(group_id: str, authorization: Optional[str] = Header(default=None)) -> dict:
    user = current_user(authorization)
    group = db.get_group(group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Группа не найдена")
    if user["id"] not in group["members"]:
        raise HTTPException(status_code=403, detail="Нет доступа")
    return {
        "id": group["id"],
        "name": group["name"],
        "owner": user["id"] == group["owner_id"],
        "created_at": group["created_at"],
        "members": _public_group_members(group),
    }


@app.post("/api/groups/{group_id}/members")
def add_member(group_id: str, payload: AddMemberPayload,
               authorization: Optional[str] = Header(default=None)) -> dict:
    user = current_user(authorization)
    group = db.get_group(group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Группа не найдена")
    if user["id"] not in group["members"]:
        raise HTTPException(status_code=403, detail="Нет доступа")
    other = db.get_user_by_username(payload.username.strip())
    if not other:
        raise HTTPException(status_code=404, detail=f"Игрок «{payload.username}» не найден")
    db.add_group_member(group_id, other["id"])
    return {"ok": True, "member_count": len(db.get_group(group_id)["members"])}


@app.post("/api/groups/{group_id}/leave")
def leave_group(group_id: str, authorization: Optional[str] = Header(default=None)) -> dict:
    user = current_user(authorization)
    group = db.get_group(group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Группа не найдена")
    db.remove_group_member(group_id, user["id"])
    remaining = db.get_group(group_id)
    if remaining and not remaining["members"]:
        db.delete_group(group_id)
    elif remaining and group["owner_id"] == user["id"]:
        db.set_group_owner(group_id, remaining["members"][0])
    return {"ok": True}


@app.post("/api/groups/{group_id}/delete")
def remove_group(group_id: str, authorization: Optional[str] = Header(default=None)) -> dict:
    user = current_user(authorization)
    group = db.get_group(group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Группа не найдена")
    if group["owner_id"] != user["id"]:
        raise HTTPException(status_code=403, detail="Удалять может только владелец")
    db.delete_group(group_id)
    return {"ok": True}


# --- админ ------------------------------------------------------------------

def _admin_user_row(u: dict) -> dict:
    has_avatar = db.has_media(u["id"], "avatar")
    has_skin = db.has_media(u["id"], "skin")
    return {
        "id": u["id"],
        "username": u["username"],
        "email": u["email"],
        "uuid": u["uuid"],
        "is_admin": bool(u["is_admin"]),
        "created_at": u["created_at"],
        "last_login": u["last_login"],
        "has_avatar": has_avatar,
        "avatar_url": f"/api/avatar/{u['uuid']}" if has_avatar else None,
        "has_skin": has_skin,
        "skin_url": f"/api/skin/{u['uuid']}" if has_skin else None,
        "groups": len(db.list_groups_for_user(u["id"])),
    }


class AdminFlagPayload(BaseModel):
    admin: bool = True


class AdminUnlockPayload(BaseModel):
    password: str


@app.post("/api/admin/unlock")
def admin_unlock(payload: AdminUnlockPayload) -> dict:
    digest = hashlib.sha256(payload.password.encode("utf-8")).hexdigest()
    if digest != ADMIN_PASSWORD_HASH:
        raise HTTPException(status_code=401, detail="Неверный пароль")
    key = sec.new_token()
    _admin_keys[key] = time.time() + ADMIN_KEY_TTL
    return {"ok": True, "key": key, "ttl": ADMIN_KEY_TTL}


@app.get("/api/admin/users")
def admin_users(authorization: Optional[str] = Header(default=None),
                admin_key: Optional[str] = Header(default=None, alias="X-Admin-Key")) -> dict:
    require_admin(authorization, admin_key)
    now = int(time.time())
    all_users = db.list_users()
    users = [_admin_user_row(u) for u in all_users]
    users.sort(key=lambda u: u.get("last_login") or 0, reverse=True)
    stats = {
        "total": len(all_users),
        "admins": sum(1 for u in all_users if u["is_admin"]),
        "with_skin": sum(1 for u in all_users if db.has_media(u["id"], "skin")),
        "with_avatar": sum(1 for u in all_users if db.has_media(u["id"], "avatar")),
        "online_24h": sum(1 for u in all_users if u["last_login"] and now - u["last_login"] < 86400),
        "online_7d": sum(1 for u in all_users if u["last_login"] and now - u["last_login"] < 604800),
        "groups": db.count_groups(),
    }
    return {"users": users, "stats": stats}


@app.get("/api/admin/users/{user_uuid}")
def admin_user_detail(user_uuid: str, authorization: Optional[str] = Header(default=None),
                      admin_key: Optional[str] = Header(default=None, alias="X-Admin-Key")) -> dict:
    require_admin(authorization, admin_key)
    u = db.get_user_by_uuid(user_uuid)
    if not u:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    row = _admin_user_row(u)
    row["groups"] = [
        {
            "id": g["id"],
            "name": g["name"],
            "owner": g["owner_id"] == u["id"],
            "member_count": g["member_count"],
            "created_at": g["created_at"],
        }
        for g in db.list_groups_for_user(u["id"])
    ]
    return row


@app.post("/api/admin/users/{user_uuid}/admin")
def admin_set_admin(user_uuid: str, payload: AdminFlagPayload,
                    authorization: Optional[str] = Header(default=None),
                    admin_key: Optional[str] = Header(default=None, alias="X-Admin-Key")) -> dict:
    require_admin(authorization, admin_key)
    u = db.get_user_by_uuid(user_uuid)
    if not u:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    db.set_admin(u["id"], payload.admin)
    return {"ok": True, "is_admin": payload.admin}


# --- статика (сайт регистрации) --------------------------------------------

_site_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "site")
if os.path.isdir(_site_dir):
    app.mount("/", StaticFiles(directory=_site_dir, html=True), name="site")
