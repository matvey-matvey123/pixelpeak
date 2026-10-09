"""Хеширование паролей и токены сессий."""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets

_ITERATIONS = 200_000
_ALGO = "pbkdf2_sha256"


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _ITERATIONS)
    return f"{_ALGO}${_ITERATIONS}${base64.b64encode(salt).decode()}${base64.b64encode(dk).decode()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, iters, salt_b64, hash_b64 = stored.split("$")
        if algo != _ALGO:
            return False
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(hash_b64)
        dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, int(iters))
        return hmac.compare_digest(dk, expected)
    except Exception:
        return False


def new_token() -> str:
    return secrets.token_urlsafe(48)


# --- signed launcher tokens (HMAC) ------------------------------------------

_SECRET = os.environ.get("PIXELPEAK_SECRET") or "pixelpeak-dev-secret-change-me"


def sign_launcher_token(payload: str) -> str:
    """Возвращает base64(payload).hmac — компактный токен для лаунчера."""
    body = base64.urlsafe_b64encode(payload.encode("utf-8")).decode().rstrip("=")
    sig = hmac.new(_SECRET.encode("utf-8"), body.encode("ascii"), hashlib.sha256).hexdigest()
    return f"{body}.{sig}"


def verify_launcher_token(token: str) -> str | None:
    try:
        body, sig = token.split(".", 1)
        expected = hmac.new(
            _SECRET.encode("utf-8"), body.encode("ascii"), hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(sig, expected):
            return None
        padded = body + "=" * (-len(body) % 4)
        return base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8")
    except Exception:
        return None
