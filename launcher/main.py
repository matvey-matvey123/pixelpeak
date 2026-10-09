"""PixelPeak Launcher — точка входа."""
from __future__ import annotations

import os
import sys
from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from core.auth import AuthManager
from core.log import get_logger, setup_logging

setup_logging()

from ui.login_window import LoginWindow
from ui.main_window import MainWindow
from ui.styles import QSS

log = get_logger()

APP_ID = "PixelPeak.Launcher.1"


def load_icon() -> QIcon:
    for name in ("icon.ico", "icon.png"):
        path = BASE_DIR / "assets" / name
        if path.exists():
            return QIcon(str(path))
    return QIcon()


def main() -> int:
    if sys.platform == "win32":
        try:
            import ctypes

            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
        except Exception:
            pass

    app = QApplication(sys.argv)
    app.setApplicationName("PixelPeak")
    app.setApplicationDisplayName("PixelPeak")
    app.setOrganizationName("PixelPeak")
    app.setStyleSheet(QSS)
    app.setWindowIcon(load_icon())

    state: dict[str, object] = {}

    def show_login() -> None:
        old = state.get("login")
        if isinstance(old, LoginWindow):
            old.deleteLater()
        win = LoginWindow()
        win.setWindowIcon(app.windowIcon())
        win.logged_in.connect(on_logged_in)
        state["login"] = win
        win.show()

    def on_logged_in(account) -> None:
        login = state.get("login")
        if isinstance(login, LoginWindow):
            login.hide()
        main_win = MainWindow(account)
        main_win.setWindowIcon(app.windowIcon())
        main_win.logged_out.connect(show_login)
        state["main"] = main_win
        main_win.show()

    account = None
    try:
        account = AuthManager().restore()
    except Exception:
        log.exception("Не удалось восстановить сессию")

    if account and account.username:
        on_logged_in(account)
    else:
        show_login()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
