"""HTTP-клиент к бэкенду PixelPeak."""
from __future__ import annotations

import logging
from typing import Any, Optional

import requests

from .config import CONFIG

log = logging.getLogger("pixelpeak.api")


class ApiError(Exception):
    pass


class PixelPeakAPI:
    def __init__(self, base: Optional[str] = None, timeout: int = 15) -> None:
        self.base = (base or CONFIG.get("api_base") or "").rstrip("/")
        self.timeout = timeout
        log.debug("api base = %s", self.base)

    def _url(self, path: str) -> str:
        return f"{self.base}{path}"

    def _handle(self, resp: requests.Response) -> dict:
        log.debug("%s %s -> %s", resp.request.method, resp.url, resp.status_code)
        try:
            data = resp.json()
        except Exception:
            data = {}
            log.debug("non-json response: %r", resp.text[:500])
        if not resp.ok:
            detail = data.get("detail") or data.get("message") or f"HTTP {resp.status_code}"
            if isinstance(detail, list):
                detail = ", ".join(str(d.get("msg", d)) for d in detail)
            log.warning("API error %s: %s", resp.status_code, detail)
            raise ApiError(str(detail))
        return data

    def health(self) -> dict:
        return self._handle(requests.get(self._url("/api/health"), timeout=self.timeout))

    def register(self, username: str, email: str, password: str) -> dict:
        resp = requests.post(
            self._url("/api/register"),
            json={"username": username, "email": email, "password": password},
            timeout=self.timeout,
        )
        return self._handle(resp)

    def login(self, username: str, password: str) -> dict:
        resp = requests.post(
            self._url("/api/login"),
            json={"username": username, "password": password},
            timeout=self.timeout,
        )
        return self._handle(resp)

    def user_exists(self, username: str) -> bool:
        resp = requests.get(
            self._url("/api/user_exists"),
            params={"username": username},
            timeout=self.timeout,
        )
        try:
            return bool(self._handle(resp).get("exists"))
        except ApiError:
            return False

    def me(self, token: str) -> dict:
        resp = requests.get(
            self._url("/api/me"),
            headers={"Authorization": f"Bearer {token}"},
            timeout=self.timeout,
        )
        return self._handle(resp)

    def fetch_avatar(self, uuid: str) -> Optional[bytes]:
        """Возвращает байты аватарки или None, если её нет."""
        if not uuid:
            return None
        try:
            resp = requests.get(self._url(f"/api/avatar/{uuid}"), timeout=self.timeout)
            if resp.ok and resp.content:
                return resp.content
        except Exception:
            pass
        return None

    def logout(self, token: str) -> None:
        try:
            requests.post(
                self._url("/api/logout"),
                headers={"Authorization": f"Bearer {token}"},
                timeout=self.timeout,
            )
        except Exception:
            pass
