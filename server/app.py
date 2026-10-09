"""PixelPeak API — регистрация, вход и сессии аккаунтов.

Запуск:
    uvicorn app:app --host 0.0.0.0 --port 8000
"""
from __future__ import annotations

import os
import re
import time
from typing import Optional

from fastapi import FastAPI, HTTPException, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, field_validator

import database as db
import security as sec

SESSION_TTL = 60 * 60 * 24 * 30  # 30 дней

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


def public_user(user: dict) -> dict:
    return {
        "id": user["id"],
        "username": user["username"],
        "email": user["email"],
        "uuid": user["uuid"],
        "is_admin": bool(user["is_admin"]),
        "created_at": user["created_at"],
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


@app.post("/api/logout")
def logout(authorization: Optional[str] = Header(default=None)) -> dict:
    token = _bearer(authorization)
    if token:
        db.delete_session(token)
    return {"ok": True}


@app.get("/api/me")
def me(authorization: Optional[str] = Header(default=None)) -> dict:
    return public_user(current_user(authorization))


# --- статика (сайт регистрации) --------------------------------------------

_site_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "site")
if os.path.isdir(_site_dir):
    app.mount("/", StaticFiles(directory=_site_dir, html=True), name="site")
