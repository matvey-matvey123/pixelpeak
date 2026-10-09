"""Тёмная тема PixelPeak (QSS)."""

ACCENT = "#7c5cff"
ACCENT2 = "#4ad6ff"

QSS = f"""
* {{
    font-family: "Segoe UI", "Inter", sans-serif;
    color: #eef0ff;
}}

QWidget#Root, QMainWindow, QDialog {{
    background-color: #0b0d17;
}}

QWidget#Sidebar {{
    background-color: #12142a;
    border-right: 1px solid #262a4d;
}}

QLabel#Logo {{
    font-size: 15px;
    font-weight: 800;
}}

QLabel#Brand {{
    font-size: 20px;
    font-weight: 800;
}}

QLabel#Muted, QLabel.muted {{ color: #9aa0c3; }}

QLabel#Avatar {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {ACCENT}, stop:1 {ACCENT2});
    color: #0b0d17;
    border-radius: 32px;
    font-size: 28px;
    font-weight: 800;
}}

QLabel#PageTitle {{
    font-size: 24px;
    font-weight: 800;
    padding: 4px 0 6px 0;
}}

QPushButton {{
    background-color: #1c2040;
    border: 1px solid #2b3060;
    border-radius: 10px;
    padding: 9px 16px;
    font-weight: 600;
}}
QPushButton:hover {{ background-color: #232850; }}
QPushButton:pressed {{ background-color: #171a33; }}
QPushButton:disabled {{ color: #6b7099; background-color: #171a33; }}

QPushButton#Primary {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {ACCENT}, stop:1 {ACCENT2});
    color: #0b0d17;
    border: none;
    font-weight: 800;
}}
QPushButton#Primary:hover {{ background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #8f74ff, stop:1 #63ddff); }}

QPushButton#Play {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {ACCENT}, stop:1 {ACCENT2});
    color: #0b0d17;
    border: none;
    border-radius: 14px;
    padding: 16px;
    font-size: 18px;
    font-weight: 800;
}}
QPushButton#Play:hover {{ background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #8f74ff, stop:1 #63ddff); }}
QPushButton#Play:disabled {{ background: #232850; color: #6b7099; }}

QPushButton#Nav {{
    background: transparent;
    border: none;
    text-align: left;
    padding: 12px 16px;
    border-radius: 10px;
    font-weight: 600;
    color: #b7bbe0;
}}
QPushButton#Nav:hover {{ background-color: #1c2040; color: #ffffff; }}
QPushButton#Nav:checked {{ background-color: #232850; color: #ffffff; }}

QComboBox, QLineEdit, QSpinBox, QDoubleSpinBox {{
    background-color: #0e1024;
    border: 1px solid #2b3060;
    border-radius: 10px;
    padding: 8px 12px;
    min-height: 22px;
}}
QComboBox:focus, QLineEdit:focus, QSpinBox:focus {{ border: 1px solid {ACCENT}; }}
QComboBox::drop-down {{ border: none; width: 24px; }}
QComboBox QAbstractItemView {{
    background-color: #12142a;
    border: 1px solid #2b3060;
    selection-background-color: #232850;
    outline: none;
}}

QCheckBox {{ spacing: 8px; }}

QProgressBar {{
    background-color: #171a33;
    border: 1px solid #262a4d;
    border-radius: 8px;
    height: 12px;
    text-align: center;
    color: transparent;
}}
QProgressBar::chunk {{
    border-radius: 7px;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {ACCENT}, stop:1 {ACCENT2});
}}

QPlainTextEdit {{
    background-color: #08090f;
    border: 1px solid #262a4d;
    border-radius: 10px;
    font-family: "Consolas", "Cascadia Mono", monospace;
    font-size: 12px;
    color: #c7ccf0;
    padding: 8px;
}}

QListWidget {{
    background-color: #12142a;
    border: 1px solid #262a4d;
    border-radius: 10px;
    padding: 6px;
    outline: none;
}}
QListWidget::item {{ padding: 8px 10px; border-radius: 8px; }}
QListWidget::item:selected {{ background-color: #232850; }}

QFrame#Card {{
    background-color: #12142a;
    border: 1px solid #262a4d;
    border-radius: 14px;
}}

QSlider::groove:horizontal {{
    height: 6px; border-radius: 3px; background: #232850;
}}
QSlider::handle:horizontal {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {ACCENT}, stop:1 {ACCENT2});
    width: 18px; margin: -7px 0; border-radius: 9px;
}}
"""
