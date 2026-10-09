"""Хранение настроек лаунчера PixelPeak."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

APP_NAME = "PixelPeak"


def appdata_dir() -> Path:
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    p = Path(base) / APP_NAME
    p.mkdir(parents=True, exist_ok=True)
    return p


DEFAULT_GAME_DIR = appdata_dir() / "minecraft"
CONFIG_PATH = appdata_dir() / "config.json"

DEFAULTS: dict[str, Any] = {
    "api_base": os.environ.get(
        "PIXELPEAK_API", "https://pixelpeak-api.matveygorvat.workers.dev"
    ),
    "username": "",
    "token": "",
    "uuid": "",
    "ram_mb": 4096,
    "max_fps": 260,
    "vsync": False,
    "skin_in_game": True,
    "java_path": "",
    "game_dir": str(DEFAULT_GAME_DIR),
    "last_version": "",
    "last_loader": "Vanilla",
    "close_on_launch": False,
}


class Config:
    def __init__(self) -> None:
        self._data: dict[str, Any] = dict(DEFAULTS)
        self.load()

    def load(self) -> None:
        if CONFIG_PATH.exists():
            try:
                loaded = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    self._data.update(loaded)
            except Exception:
                pass

    def save(self) -> None:
        try:
            CONFIG_PATH.write_text(
                json.dumps(self._data, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except Exception:
            pass

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, DEFAULTS.get(key, default))

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value
        self.save()

    def update(self, **kwargs: Any) -> None:
        self._data.update(kwargs)
        self.save()
    @property
    def game_dir(self) -> Path:
        return Path(self.get("game_dir") or str(DEFAULT_GAME_DIR))

    def clear_session(self) -> None:
        self.update(token="", uuid="")


CONFIG = Config()
