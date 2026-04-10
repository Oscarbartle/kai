from PySide6.QtWidgets import QPushButton
from PySide6.QtGui import QCursor
from PySide6.QtCore import Qt


class TagChip(QPushButton):
    """Clickable tag pill that appends its text to the tags input."""

    def __init__(self, tag_name, on_click):
        super().__init__(tag_name)
        self._tag = tag_name
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setFixedHeight(26)
        self.setProperty("btn", "chip")
        self.clicked.connect(lambda: on_click(self._tag))
