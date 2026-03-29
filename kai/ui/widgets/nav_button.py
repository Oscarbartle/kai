from kai.ui import theme

from PySide6.QtWidgets import QPushButton
from PySide6.QtCore import Qt

class NavButton(QPushButton):
    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)

        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(42)
        self.setCheckable(True)
        self.setStyleSheet(self._build_style())

    def _build_style(self):
        t = theme.theme()
        return f"""
            QPushButton {{
                background-color: transparent;
                color: {t.text_dim};
                border: none;
                border-radius: 8px;
                padding: 8px 14px;
                text-align: left;
                font-size: 13px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {t.card};
                color: {t.text};
            }}
            QPushButton:checked {{
                background-color: {t.card};
                color: {t.text};
                border-left: 3px solid {t.accent};
            }}
        """
