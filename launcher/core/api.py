"""HTTP-клиент к бэкенду PixelPeak."""
from __future__ import annotations

from typing import Any, Optional

import requests

from .config import CONFIG


class ApiError(Exception):
    pass


class PixelPeakAPI:
    def __init__(self, base: Optional[str] = None, timeout: int = 15) -> None:
        self.base = (base or CONFIG.get("api_base") or "").rstrip("/")
        self.timeout = timeout

    def _url(self, path: str) -> str:
        return f"{self.base}{path}"

    def _handle(self, resp: requests.Response) -> dict:
        try:
            data = resp.json()
        except Exception:
            data = {}
        if not resp.ok:
            detail = data.get("detail") or data.get("message") or f"HTTP {resp.status_code}"
            if isinstance(detail, list):
                detail = ", ".join(str(d.get("msg", d)) for d in detail)
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

    def me(self, token: str) -> dict:
        resp = requests.get(
            self._url("/api/me"),
            headers={"Authorization": f"Bearer {token}"},
            timeout=self.timeout,
        )
        return self._handle(resp)

    def logout(self, token: str) -> None:
        try:
            requests.post(
                self._url("/api/logout"),
                headers={"Authorization": f"Bearer {token}"},
                timeout=self.timeout,
            )
        except Exception:
            pass
