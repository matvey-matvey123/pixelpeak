"""Логирование лаунчера в файл (для диагностики)."""
from __future__ import annotations

import logging
import sys
import traceback
from pathlib import Path

from .config import appdata_dir

LOG_PATH = appdata_dir() / "launcher.log"

_configured = False


def setup_logging() -> Path:
    global _configured
    if _configured:
        return LOG_PATH
    _configured = True
    try:
        LOG_PATH.write_text("", encoding="utf-8")
    except Exception:
        pass
    handlers: list[logging.Handler] = [
        logging.FileHandler(LOG_PATH, encoding="utf-8"),
    ]
    if sys.stderr is not None:
        handlers.append(logging.StreamHandler(sys.stderr))
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        handlers=handlers,
    )
    sys.excepthook = _excepthook
    logging.getLogger("pixelpeak").info("Launcher started (log: %s)", LOG_PATH)
    return LOG_PATH


def _excepthook(exc_type, exc_value, exc_tb) -> None:
    logging.getLogger("pixelpeak").critical(
        "Unhandled exception:\n%s", "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
    )


def get_logger(name: str = "pixelpeak") -> logging.Logger:
    return logging.getLogger(name)
