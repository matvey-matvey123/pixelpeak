"""Фоновые потоки: вход, установка версий и запуск игры."""
from __future__ import annotations

import logging
import os
import subprocess
import sys
from typing import Optional

from PySide6.QtCore import QThread, Signal

from core.auth import AuthManager
from core.minecraft import Minecraft, MinecraftError

log = logging.getLogger("pixelpeak.workers")


def _make_callback(signals: "InstallWorker") -> dict:
    return {
        "setStatus": lambda text: signals.status.emit(str(text)),
        "setProgress": lambda value: signals.progress.emit(int(value)),
        "setMax": lambda value: signals.maximum.emit(int(value)),
    }


class LoginWorker(QThread):
    success = Signal(object)
    failed = Signal(str)
    status = Signal(str)
    needs_password = Signal(str)

    def __init__(self, mode: str, username: str, password: str = "", email: str = "") -> None:
        super().__init__()
        self.mode = mode
        self.username = username
        self.password = password
        self.email = email

    def run(self) -> None:
        auth = AuthManager()
        log.info("login worker: mode=%s username=%r", self.mode, self.username)
        try:
            if self.mode == "offline":
                self.status.emit("Проверяем ник...")
                try:
                    from core.api import PixelPeakAPI

                    exists = PixelPeakAPI().user_exists(self.username)
                    log.debug("user_exists(%r) = %s", self.username, exists)
                    if exists:
                        self.needs_password.emit(self.username)
                        return
                except Exception as e:
                    log.warning("user_exists check failed: %s", e)
                self.status.emit("Вход по нику (офлайн)...")
                acc = auth.login_offline(self.username)
            elif self.mode == "register":
                self.status.emit("Создаём аккаунт...")
                acc = auth.register(self.username, self.email, self.password)
            else:
                self.status.emit("Подключаемся к PixelPeak...")
                acc = auth.login(self.username, self.password)
            log.info("login worker success: %s", getattr(acc, "username", acc))
            self.success.emit(acc)
        except Exception as e:
            log.exception("login worker failed")
            self.failed.emit(str(e))


class InstallWorker(QThread):
    status = Signal(str)
    progress = Signal(int)
    maximum = Signal(int)
    finished_ok = Signal(str)
    failed = Signal(str)

    def __init__(self, mc: Minecraft, version: str, loader: str, java: Optional[str] = None) -> None:
        super().__init__()
        self.mc = mc
        self.version = version
        self.loader = loader
        self.java = java

    def run(self) -> None:
        try:
            self.status.emit(f"Установка {self.version} ({self.loader})...")
            version_id = self.mc.install(
                self.version, self.loader, callback=_make_callback(self), java=self.java
            )
            self.finished_ok.emit(version_id)
        except MinecraftError as e:
            self.failed.emit(str(e))
        except Exception as e:
            self.failed.emit(f"Ошибка установки: {e}")


class VersionListWorker(QThread):
    loaded = Signal(list)
    failed = Signal(str)

    def __init__(self, mc: Minecraft) -> None:
        super().__init__()
        self.mc = mc

    def run(self) -> None:
        try:
            self.loaded.emit(self.mc.all_versions())
        except Exception as e:
            self.failed.emit(str(e))


class LaunchWorker(QThread):
    log = Signal(str)
    started = Signal()
    exited = Signal(int)
    failed = Signal(str)

    def __init__(self, command: list[str], cwd: str) -> None:
        super().__init__()
        self.command = command
        self.cwd = cwd
        self._proc: Optional[subprocess.Popen] = None

    def run(self) -> None:
        try:
            if self.cwd:
                os.makedirs(self.cwd, exist_ok=True)
            java = self.command[0] if self.command else ""
            if java and not os.path.isfile(java):
                raise MinecraftError(
                    f"Не найден файл Java: {java}. Укажи путь к java.exe в настройках."
                )
            flags = 0
            if sys.platform == "win32":
                flags = subprocess.CREATE_NO_WINDOW  # type: ignore[attr-defined]
            self._proc = subprocess.Popen(
                self.command,
                cwd=self.cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                encoding="utf-8",
                errors="replace",
                creationflags=flags,
            )
            self.started.emit()
            assert self._proc.stdout is not None
            for line in self._proc.stdout:
                self.log.emit(line.rstrip("\n"))
            code = self._proc.wait()
            self.exited.emit(code)
        except Exception as e:
            self.failed.emit(str(e))

    def stop(self) -> None:
        if self._proc and self._proc.poll() is None:
            try:
                self._proc.terminate()
            except Exception:
                pass
