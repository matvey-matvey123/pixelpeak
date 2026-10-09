"""Окно входа/регистрации PixelPeak."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.config import CONFIG
from ui.workers import LoginWorker


class LoginWindow(QWidget):
    logged_in = Signal(object)

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("Root")
        self.setWindowTitle("PixelPeak — вход")
        self.setFixedSize(460, 640)
        self.mode = "login"
        self._worker: LoginWorker | None = None
        self._build()

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(40, 40, 40, 40)
        root.setSpacing(14)

        brand = QLabel("PixelPeak")
        brand.setObjectName("Brand")
        brand.setAlignment(Qt.AlignCenter)
        root.addWidget(brand)

        card = QFrame()
        card.setObjectName("Card")
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(40)
        shadow.setColor(Qt.black)
        card.setGraphicsEffect(shadow)
        root.addWidget(card)

        form = QVBoxLayout(card)
        form.setContentsMargins(26, 26, 26, 26)
        form.setSpacing(12)

        self.title = QLabel("Вход в аккаунт")
        self.title.setObjectName("PageTitle")
        form.addWidget(self.title)

        self.hint = QLabel("Используй ник или email и пароль.")
        self.hint.setObjectName("Muted")
        form.addWidget(self.hint)

        self.username = QLineEdit()
        self.username.setPlaceholderText("Ник")
        form.addWidget(self.username)

        self.email = QLineEdit()
        self.email.setPlaceholderText("Email")
        self.email.setVisible(False)
        form.addWidget(self.email)

        self.password = QLineEdit()
        self.password.setPlaceholderText("Пароль")
        self.password.setEchoMode(QLineEdit.Password)
        form.addWidget(self.password)

        self.offline = QCheckBox("Офлайн-режим (только ник, без аккаунта)")
        form.addWidget(self.offline)

        self.status = QLabel("")
        self.status.setObjectName("Muted")
        self.status.setWordWrap(True)
        form.addWidget(self.status)

        self.submit = QPushButton("Войти")
        self.submit.setObjectName("Primary")
        self.submit.clicked.connect(self._submit)
        form.addWidget(self.submit)

        self.switch = QPushButton("Нет аккаунта? Зарегистрироваться")
        self.switch.setObjectName("Nav")
        self.switch.setCursor(Qt.PointingHandCursor)
        self.switch.clicked.connect(self._switch_mode)
        form.addWidget(self.switch)

        site = QPushButton("Открыть сайт PixelPeak")
        site.setObjectName("Nav")
        site.setCursor(Qt.PointingHandCursor)
        site.clicked.connect(self._open_site)
        form.addWidget(site)

        root.addStretch(1)

        advanced = QHBoxLayout()
        adv_label = QLabel("API:")
        adv_label.setObjectName("Muted")
        advanced.addWidget(adv_label)
        self.api_edit = QLineEdit(CONFIG.get("api_base"))
        self.api_edit.setPlaceholderText("http://127.0.0.1:8000")
        self.api_edit.editingFinished.connect(self._save_api)
        advanced.addWidget(self.api_edit, 1)
        root.addLayout(advanced)

        self.offline.toggled.connect(self._on_offline)
        self._apply_mode()

    # --- режимы -------------------------------------------------------------

    def _on_offline(self, checked: bool) -> None:
        self._apply_mode()

    def _apply_mode(self) -> None:
        offline = self.offline.isChecked()
        register = self.mode == "register"

        if offline:
            self.title.setText("Офлайн-вход")
            self.hint.setText("Введи ник, аккаунт не нужен.")
            self.email.setVisible(False)
            self.password.setVisible(False)
            self.switch.setVisible(False)
            self.submit.setText("Играть")
        elif register:
            self.title.setText("Создание аккаунта")
            self.hint.setText("Аккаунт будет работать и на сайте, и в лаунчере.")
            self.email.setVisible(True)
            self.password.setVisible(True)
            self.switch.setText("Уже есть аккаунт? Войти")
            self.submit.setText("Зарегистрироваться")
            self.switch.setVisible(True)
        else:
            self.title.setText("Вход в аккаунт")
            self.hint.setText("Используй ник или email и пароль.")
            self.email.setVisible(False)
            self.password.setVisible(True)
            self.switch.setText("Нет аккаунта? Зарегистрироваться")
            self.submit.setText("Войти")
            self.switch.setVisible(True)

    def _switch_mode(self) -> None:
        self.mode = "register" if self.mode == "login" else "login"
        self._apply_mode()

    def _save_api(self) -> None:
        CONFIG.set("api_base", self.api_edit.text().strip())

    def _open_site(self) -> None:
        QDesktopServices.openUrl(QUrl(CONFIG.get("api_base")))

    # --- отправка -----------------------------------------------------------

    def _submit(self) -> None:
        username = self.username.text().strip()
        if not username:
            self.status.setText("Введи ник")
            return

        if self.offline.isChecked():
            mode = "offline"
        else:
            mode = self.mode
            if not self.password.text():
                self.status.setText("Введи пароль")
                return
            if mode == "register" and not self.email.text().strip():
                self.status.setText("Введи email")
                return

        self._set_busy(True)
        self.status.setText("Подключение...")
        self._worker = LoginWorker(
            mode,
            username,
            password=self.password.text(),
            email=self.email.text().strip(),
        )
        self._worker.success.connect(self._on_success)
        self._worker.failed.connect(self._on_failed)
        self._worker.status.connect(self.status.setText)
        self._worker.start()

    def _set_busy(self, busy: bool) -> None:
        self.submit.setEnabled(not busy)
        self.switch.setEnabled(not busy)
        self.offline.setEnabled(not busy)

    def _on_success(self, account) -> None:
        self._set_busy(False)
        self.status.setText(f"Привет, {account.username}!")
        self.logged_in.emit(account)

    def _on_failed(self, message: str) -> None:
        self._set_busy(False)
        self.status.setText(message)
