"""Главное окно лаунчера PixelPeak."""
from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QIcon
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSlider,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from core.config import CONFIG
from core.minecraft import LOADERS, Minecraft, MinecraftError
from ui.workers import InstallWorker, LaunchWorker, VersionListWorker


class MainWindow(QWidget):
    logged_out = Signal()

    def __init__(self, account) -> None:
        super().__init__()
        self.account = account
        self.is_offline = not bool(getattr(account, "email", ""))
        self.mc = Minecraft(CONFIG.get("game_dir"))
        self.versions: list[dict] = []
        self._install_worker: InstallWorker | None = None
        self._launch_worker: LaunchWorker | None = None
        self._list_worker: VersionListWorker | None = None

        self.setObjectName("Root")
        self.setWindowTitle("PixelPeak")
        self.resize(1000, 680)
        self._build()
        self._load_versions()
        self._update_java_hint()

    # ------------------------------------------------------------------ UI --
    def _build(self) -> None:
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_sidebar())

        self.pages = QStackedWidget()
        self.pages.addWidget(self._build_play_page())
        self.pages.addWidget(self._build_versions_page())
        self.pages.addWidget(self._build_settings_page())
        self.pages.addWidget(self._build_console_page())
        root.addWidget(self.pages, 1)

    def _build_sidebar(self) -> QWidget:
        side = QWidget()
        side.setObjectName("Sidebar")
        side.setFixedWidth(230)
        lay = QVBoxLayout(side)
        lay.setContentsMargins(18, 24, 18, 20)
        lay.setSpacing(14)

        brand = QLabel("PixelPeak")
        brand.setObjectName("Brand")
        lay.addWidget(brand)

        self.avatar = QLabel(self.account.username[:1].upper())
        self.avatar.setObjectName("Avatar")
        self.avatar.setFixedSize(64, 64)
        self.avatar.setAlignment(Qt.AlignCenter)
        lay.addWidget(self.avatar, alignment=Qt.AlignHCenter)

        name = QLabel(self.account.username)
        name.setAlignment(Qt.AlignCenter)
        name.setStyleSheet("font-weight: 700;")
        lay.addWidget(name)

        sub = QLabel("офлайн" if self.is_offline else (getattr(self.account, "email", "") or "аккаунт"))
        sub.setObjectName("Muted")
        sub.setAlignment(Qt.AlignCenter)
        sub.setWordWrap(True)
        lay.addWidget(sub)

        lay.addSpacing(10)

        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)
        for idx, text in enumerate(["Играть", "Версии", "Настройки", "Консоль"]):
            btn = QPushButton(text)
            btn.setObjectName("Nav")
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda _=False, i=idx: self.pages.setCurrentIndex(i))
            self.nav_group.addButton(btn, idx)
            lay.addWidget(btn)
            if idx == 0:
                btn.setChecked(True)

        lay.addStretch(1)

        logout = QPushButton("Выйти")
        logout.setObjectName("Nav")
        logout.setCursor(Qt.PointingHandCursor)
        logout.clicked.connect(self._logout)
        lay.addWidget(logout)

        return side

    # --- страница «Играть» --------------------------------------------------
    def _build_play_page(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(34, 28, 34, 28)
        lay.setSpacing(16)

        title = QLabel("Играть")
        title.setObjectName("PageTitle")
        lay.addWidget(title)

        card = QFrame()
        card.setObjectName("Card")
        grid = QGridLayout(card)
        grid.setContentsMargins(24, 24, 24, 24)
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(14)

        grid.addWidget(self._label("Ник"), 0, 0)
        self.nick = QLineEdit(self.account.username)
        if not self.is_offline:
            self.nick.setEnabled(False)
            self.nick.setToolTip("Ник привязан к аккаунту PixelPeak")
        else:
            self.nick.setToolTip("Можно изменить ник (офлайн-режим)")
        grid.addWidget(self.nick, 0, 1, 1, 3)

        grid.addWidget(self._label("Версия"), 1, 0)
        self.version_combo = QComboBox()
        self.version_combo.setEditable(True)
        grid.addWidget(self.version_combo, 1, 1, 1, 2)
        refresh = QPushButton("Обновить")
        refresh.clicked.connect(self._load_versions)
        grid.addWidget(refresh, 1, 3)

        grid.addWidget(self._label("Загрузчик"), 2, 0)
        self.loader_combo = QComboBox()
        for key, name in [("vanilla", "Vanilla"), ("fabric", "Fabric"), ("forge", "Forge"), ("neoforge", "NeoForge")]:
            self.loader_combo.addItem(name, key)
        idx = self.loader_combo.findData(CONFIG.get("last_loader", "vanilla"))
        self.loader_combo.setCurrentIndex(max(0, idx))
        grid.addWidget(self.loader_combo, 2, 1)

        grid.addWidget(self._label("ОЗУ"), 2, 2)
        ram_row = QHBoxLayout()
        self.ram = QSlider(Qt.Horizontal)
        self.ram.setRange(1024, 32768)
        self.ram.setSingleStep(512)
        self.ram.setPageStep(1024)
        self.ram.setValue(int(CONFIG.get("ram_mb", 4096)))
        self.ram_label = QLabel(f"{self.ram.value()} МБ")
        self.ram.valueChanged.connect(lambda v: self.ram_label.setText(f"{v} МБ"))
        ram_row.addWidget(self.ram, 1)
        ram_row.addWidget(self.ram_label)
        grid.addLayout(ram_row, 2, 3)

        lay.addWidget(card)
        lay.addSpacing(4)

        self.play_btn = QPushButton("ИГРАТЬ")
        self.play_btn.setObjectName("Play")
        self.play_btn.setCursor(Qt.PointingHandCursor)
        self.play_btn.clicked.connect(self._play)
        lay.addWidget(self.play_btn)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        lay.addWidget(self.progress)

        self.status = QLabel("Готов к запуску")
        self.status.setObjectName("Muted")
        lay.addWidget(self.status)

        self.play_log = QPlainTextEdit()
        self.play_log.setReadOnly(True)
        self.play_log.setPlaceholderText("Здесь появятся сообщения установки и запуска...")
        lay.addWidget(self.play_log, 1)

        return page

    # --- страница «Версии» --------------------------------------------------
    def _build_versions_page(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(34, 28, 34, 28)
        lay.setSpacing(12)

        title = QLabel("Версии")
        title.setObjectName("PageTitle")
        lay.addWidget(title)

        top = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Поиск версии...")
        self.search.textChanged.connect(self._filter_versions)
        top.addWidget(self.search, 1)

        self.ver_loader = QComboBox()
        for key, name in [("vanilla", "Vanilla"), ("fabric", "Fabric"), ("forge", "Forge"), ("neoforge", "NeoForge")]:
            self.ver_loader.addItem(name, key)
        top.addWidget(self.ver_loader)

        install_btn = QPushButton("Установить")
        install_btn.setObjectName("Primary")
        install_btn.clicked.connect(self._install_selected)
        top.addWidget(install_btn)
        lay.addLayout(top)

        self.version_list = QListWidget()
        lay.addWidget(self.version_list, 1)

        self.ver_status = QLabel("")
        self.ver_status.setObjectName("Muted")
        lay.addWidget(self.ver_status)

        return page

    # --- страница «Настройки» ----------------------------------------------
    def _build_settings_page(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(34, 28, 34, 28)
        lay.setSpacing(14)

        title = QLabel("Настройки")
        title.setObjectName("PageTitle")
        lay.addWidget(title)

        card = QFrame()
        card.setObjectName("Card")
        grid = QGridLayout(card)
        grid.setContentsMargins(24, 24, 24, 24)
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(14)

        def row(r: int, label: str, widget: QWidget, *buttons: QWidget) -> None:
            grid.addWidget(self._label(label), r, 0)
            grid.addWidget(widget, r, 1)
            col = 2
            for b in buttons:
                grid.addWidget(b, r, col)
                col += 1

        self.set_api = QLineEdit(CONFIG.get("api_base"))
        row(0, "API-сервер", self.set_api)

        self.set_java = QLineEdit(CONFIG.get("java_path"))
        self.set_java.setPlaceholderText("(определится автоматически)")
        java_browse = QPushButton("Обзор")
        java_browse.clicked.connect(self._browse_java)
        java_auto = QPushButton("Авто")
        java_auto.clicked.connect(self._auto_java)
        row(1, "Java", self.set_java, java_browse, java_auto)

        self.set_dir = QLineEdit(str(CONFIG.game_dir))
        dir_browse = QPushButton("Обзор")
        dir_browse.clicked.connect(self._browse_dir)
        dir_open = QPushButton("Открыть")
        dir_open.clicked.connect(self._open_dir)
        row(2, "Папка игры", self.set_dir, dir_browse, dir_open)

        self.set_ram = QSpinBox()
        self.set_ram.setRange(1024, 32768)
        self.set_ram.setSingleStep(512)
        self.set_ram.setSuffix(" МБ")
        self.set_ram.setValue(int(CONFIG.get("ram_mb", 4096)))
        row(3, "ОЗУ по умолчанию", self.set_ram)

        self.set_close = QCheckBox("Закрывать лаунчер после запуска игры")
        self.set_close.setChecked(bool(CONFIG.get("close_on_launch", False)))
        grid.addWidget(self.set_close, 4, 1)

        self.java_hint = QLabel("")
        self.java_hint.setObjectName("Muted")
        self.java_hint.setWordWrap(True)
        grid.addWidget(self.java_hint, 5, 0, 1, 3)

        lay.addWidget(card)

        save = QPushButton("Сохранить настройки")
        save.setObjectName("Primary")
        save.clicked.connect(self._save_settings)
        lay.addWidget(save)

        self.settings_status = QLabel("")
        self.settings_status.setObjectName("Muted")
        lay.addWidget(self.settings_status)

        lay.addStretch(1)
        return page

    # --- страница «Консоль» -------------------------------------------------
    def _build_console_page(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(34, 28, 34, 28)
        lay.setSpacing(12)

        header = QHBoxLayout()
        title = QLabel("Консоль")
        title.setObjectName("PageTitle")
        header.addWidget(title)
        header.addStretch(1)
        clear = QPushButton("Очистить")
        clear.clicked.connect(lambda: self.console.clear())
        header.addWidget(clear)
        lay.addLayout(header)

        self.console = QPlainTextEdit()
        self.console.setReadOnly(True)
        self.console.setPlaceholderText("Вывод игры появится здесь.")
        lay.addWidget(self.console, 1)
        return page

    # --- хелперы ------------------------------------------------------------
    @staticmethod
    def _label(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("Muted")
        return lbl

    # --- версии -------------------------------------------------------------
    def _load_versions(self) -> None:
        self.status.setText("Загружаем список версий...")
        self._list_worker = VersionListWorker(self.mc)
        self._list_worker.loaded.connect(self._on_versions_loaded)
        self._list_worker.failed.connect(lambda e: self.status.setText(e))
        self._list_worker.start()

    def _on_versions_loaded(self, versions: list[dict]) -> None:
        self.versions = versions
        releases = [v["id"] for v in versions if v["type"] == "release"]
        current = self.version_combo.currentText() or CONFIG.get("last_version", "")
        self.version_combo.clear()
        self.version_combo.addItems(releases)
        if current:
            i = self.version_combo.findText(current)
            if i >= 0:
                self.version_combo.setCurrentIndex(i)
            else:
                self.version_combo.setCurrentText(current)
        self._populate_version_list()
        self.status.setText(f"Доступно версий: {len(releases)} (релизы)")

    def _populate_version_list(self) -> None:
        installed = set(self.mc.installed_versions())
        self.version_list.clear()
        for v in self.versions:
            mark = "  ✔ установлено" if v["id"] in installed else ""
            item = QListWidgetItem(f"{v['id']}   [{v['type']}]{mark}")
            item.setData(Qt.UserRole, v["id"])
            self.version_list.addItem(item)

    def _filter_versions(self, text: str) -> None:
        text = text.lower().strip()
        for i in range(self.version_list.count()):
            item = self.version_list.item(i)
            item.setHidden(bool(text) and text not in item.text().lower())

    def _install_selected(self) -> None:
        item = self.version_list.currentItem()
        if item is None:
            self.ver_status.setText("Выбери версию в списке")
            return
        version = item.data(Qt.UserRole)
        loader = self.ver_loader.currentData()
        self.ver_status.setText(f"Установка {version} ({LOADERS.get(loader, loader)})...")
        w = InstallWorker(self.mc, version, loader, java=CONFIG.get("java_path") or None)
        w.status.connect(self.ver_status.setText)
        w.progress.connect(lambda p: self.progress.setValue(p))
        w.maximum.connect(lambda m: self.progress.setRange(0, max(1, m)))
        w.finished_ok.connect(lambda vid: (self.ver_status.setText(f"Готово: {vid}"), self._populate_version_list()))
        w.failed.connect(lambda e: self.ver_status.setText(f"Ошибка: {e}"))
        w.start()
        self._install_worker = w

    # --- настройки ----------------------------------------------------------
    def _browse_java(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Выбери java.exe", "", "Java (*.exe);;Все файлы (*)")
        if path:
            self.set_java.setText(path)

    def _auto_java(self) -> None:
        found = self.mc.find_best_java()
        if found:
            self.set_java.setText(found)
        else:
            self.settings_status.setText("Java не найдена, укажи путь вручную")

    def _browse_dir(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Папка игры", str(CONFIG.game_dir))
        if path:
            self.set_dir.setText(path)

    def _open_dir(self) -> None:
        path = Path(self.set_dir.text() or CONFIG.game_dir)
        path.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def _update_java_hint(self) -> None:
        found = self.mc.find_best_java()
        if found:
            self.java_hint.setText(f"Найдена Java: {found}")
        else:
            self.java_hint.setText("Java не найдена автоматически — выбери java.exe вручную.")

    def _save_settings(self) -> None:
        CONFIG.update(
            api_base=self.set_api.text().strip(),
            java_path=self.set_java.text().strip(),
            game_dir=self.set_dir.text().strip() or str(CONFIG.game_dir),
            ram_mb=self.set_ram.value(),
            close_on_launch=self.set_close.isChecked(),
        )
        self.mc = Minecraft(CONFIG.get("game_dir"))
        self.settings_status.setText("Настройки сохранены ✔")
        self._update_java_hint()

    # --- запуск -------------------------------------------------------------
    def _play(self) -> None:
        version = self.version_combo.currentText().strip()
        if not version:
            self._log_play("Сначала выбери версию.")
            return
        loader = self.loader_combo.currentData()
        CONFIG.update(last_version=version, last_loader=loader, ram_mb=self.ram.value())

        self.play_btn.setEnabled(False)
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self._log_play(f"> Подготовка {version} ({LOADERS.get(loader, loader)})...")

        self._install_worker = InstallWorker(
            self.mc, version, loader, java=CONFIG.get("java_path") or None
        )
        self._install_worker.status.connect(self.status.setText)
        self._install_worker.status.connect(self._log_play)
        self._install_worker.progress.connect(self.progress.setValue)
        self._install_worker.maximum.connect(lambda m: self.progress.setRange(0, max(1, m)))
        self._install_worker.finished_ok.connect(self._do_launch)
        self._install_worker.failed.connect(self._install_failed)
        self._install_worker.start()

    def _install_failed(self, message: str) -> None:
        self.play_btn.setEnabled(True)
        self.status.setText(f"Ошибка: {message}")
        self._log_play(f"[!] {message}")

    def _do_launch(self, version_id: str) -> None:
        self.status.setText("Запуск Minecraft...")
        self.progress.setRange(0, 0)
        self._log_play(f"> Запуск {version_id}")
        try:
            cmd = self.mc.build_command(
                version_id,
                username=self.nick.text().strip() or self.account.username,
                uuid=self.account.uuid,
                token=self.account.token,
                ram_mb=self.ram.value(),
            )
        except MinecraftError as e:
            self._install_failed(str(e))
            return

        self._launch_worker = LaunchWorker(cmd, cwd=str(self.mc.game_dir))
        self._launch_worker.log.connect(self._append_console)
        self._launch_worker.started.connect(lambda: (self.status.setText("Игра запущена"), self.progress.setRange(0, 100), self.progress.setValue(100)))
        self._launch_worker.exited.connect(self._game_exited)
        self._launch_worker.failed.connect(self._install_failed)
        self._launch_worker.start()

        if CONFIG.get("close_on_launch"):
            self.close()

    def _game_exited(self, code: int) -> None:
        self.play_btn.setEnabled(True)
        self.progress.setRange(0, 100)
        self.status.setText(f"Игра закрыта (код {code})")
        self._log_play(f"> Игра завершена, код {code}")

    # --- логи ---------------------------------------------------------------
    def _log_play(self, text: str) -> None:
        self.play_log.appendPlainText(text)
        self._append_console(text)

    def _append_console(self, text: str) -> None:
        self.console.appendPlainText(text)

    # --- выход --------------------------------------------------------------
    def _logout(self) -> None:
        from core.auth import AuthManager

        AuthManager().logout()
        self.logged_out.emit()
