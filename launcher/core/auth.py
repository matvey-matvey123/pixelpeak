"""Управление сессией аккаунта в лаунчере."""
from __future__ import annotations

import hashlib
import logging
import uuid
from dataclasses import dataclass, asdict
from typing import Optional

from .api import PixelPeakAPI
from .config import CONFIG

log = logging.getLogger("pixelpeak.auth")

OFFLINE_TOKEN = "0" * 32


@dataclass
class Account:
    username: str
    uuid: str
    email: str = ""
    token: str = ""
    is_admin: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


def offline_uuid(name: str) -> str:
    digest = bytearray(hashlib.md5(("OfflinePlayer:" + name).encode("utf-8")).digest())
    digest[6] = (digest[6] & 0x0F) | 0x30
    digest[8] = (digest[8] & 0x3F) | 0x80
    return str(uuid.UUID(bytes=bytes(digest)))


class AuthManager:
    def __init__(self) -> None:
        self.account: Optional[Account] = None

    def login(self, username: str, password: str) -> Account:
        api = PixelPeakAPI()
        data = api.login(username, password)
        user = data.get("user", {})
        acc = Account(
            username=user.get("username", username),
            uuid=user.get("uuid") or offline_uuid(username),
            email=user.get("email", ""),
            token=data.get("token", ""),
            is_admin=bool(user.get("is_admin")),
        )
        self._persist(acc)
        return acc

    def register(self, username: str, email: str, password: str) -> Account:
        api = PixelPeakAPI()
        data = api.register(username, email, password)
        user = data.get("user", {})
        acc = Account(
            username=user.get("username", username),
            uuid=user.get("uuid") or offline_uuid(username),
            email=user.get("email", ""),
            token=data.get("token", ""),
            is_admin=bool(user.get("is_admin")),
        )
        self._persist(acc)
        return acc

    def login_offline(self, nickname: str) -> Account:
        """Вход без бэкенда — только ник (офлайн режим)."""
        acc = Account(
            username=nickname,
            uuid=offline_uuid(nickname),
            token="0" * 32,
        )
        self._persist(acc)
        return acc

    def restore(self) -> Optional[Account]:
        username = CONFIG.get("username")
        if not username:
            return None
        token = CONFIG.get("token") or ""
        uuid = CONFIG.get("uuid") or ""

        if token and token != "0" * 32:
            try:
                user = PixelPeakAPI(timeout=8).me(token)
            except Exception as e:
                log.info("session restore failed (%s); нужно войти заново", e)
                return None
            acc = Account(
                username=user.get("username", username),
                uuid=user.get("uuid") or offline_uuid(username),
                email=user.get("email", ""),
                token=token,
                is_admin=bool(user.get("is_admin")),
            )
            self._persist(acc)
            log.info("session restored for %s", acc.username)
            return acc

        if uuid:
            acc = Account(username=username, uuid=uuid, token="")
            self.account = acc
            log.info("offline session restored for %s", acc.username)
            return acc
        return None

    def logout(self) -> None:
        token = CONFIG.get("token")
        if token:
            PixelPeakAPI().logout(token)
        CONFIG.clear_session()
        self.account = None

    def _persist(self, acc: Account) -> None:
        CONFIG.update(
            username=acc.username,
            uuid=acc.uuid,
            token=acc.token,
        )
        self.account = acc
