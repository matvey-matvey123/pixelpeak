"""SQLite-хранилище аккаунтов PixelPeak."""
from __future__ import annotations

import os
import sqlite3
import time
import hashlib
import uuid
from contextlib import contextmanager
from typing import Optional

DB_PATH = os.environ.get(
    "PIXELPEAK_DB",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "pixelpeak.db"),
)


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                username      TEXT UNIQUE NOT NULL,
                email         TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                uuid          TEXT NOT NULL,
                is_admin      INTEGER NOT NULL DEFAULT 0,
                created_at    INTEGER NOT NULL,
                last_login    INTEGER
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                token      TEXT PRIMARY KEY,
                user_id    INTEGER NOT NULL,
                created_at INTEGER NOT NULL,
                expires_at INTEGER NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """
        )


def offline_uuid(name: str) -> str:
    """UUID в стиле Java offline-mode (md5, version 3)."""
    digest = bytearray(hashlib.md5(("OfflinePlayer:" + name).encode("utf-8")).digest())
    digest[6] = (digest[6] & 0x0F) | 0x30
    digest[8] = (digest[8] & 0x3F) | 0x80
    return str(uuid.UUID(bytes=bytes(digest)))


def create_user(username: str, email: str, password_hash: str) -> dict:
    now = int(time.time())
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO users (username, email, password_hash, uuid, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (username, email, password_hash, offline_uuid(username), now),
        )
        user_id = cur.lastrowid
    return get_user_by_id(user_id)


def get_user_by_id(user_id: int) -> Optional[dict]:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return dict(row) if row else None


def get_user_by_username(username: str) -> Optional[dict]:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE username = ? COLLATE NOCASE", (username,)
        ).fetchone()
    return dict(row) if row else None


def get_user_by_email(email: str) -> Optional[dict]:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE email = ? COLLATE NOCASE", (email,)
        ).fetchone()
    return dict(row) if row else None


def touch_login(user_id: int) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE users SET last_login = ? WHERE id = ?", (int(time.time()), user_id)
        )


# --- sessions ---------------------------------------------------------------

def create_session(user_id: int, token: str, ttl_seconds: int) -> None:
    now = int(time.time())
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO sessions (token, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
            (token, user_id, now, now + ttl_seconds),
        )


def get_session(token: str) -> Optional[dict]:
    now = int(time.time())
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM sessions WHERE token = ? AND expires_at > ?", (token, now)
        ).fetchone()
    return dict(row) if row else None


def delete_session(token: str) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
