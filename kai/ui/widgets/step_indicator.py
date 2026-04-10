from kai.ui import theme

from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QPainter, QColor
from PySide6.QtCore import Qt


class StepDots(QWidget):
    """Horizontal dot indicator showing progress through a multi-step flow."""

    def __init__(self, count: int, parent=None):
        super().__init__(parent)
        self._count = count
        self._current = 0
        self.setFixedHeight(12)

    def set_step(self, idx: int):
        self._current = idx
        self.update()

    def paintEvent(self, event):
        t = theme.theme()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        dot_r = 4
        gap = 16
        total_w = self._count * (dot_r * 2) + (self._count - 1) * gap
        x = (self.width() - total_w) // 2
        cy = self.height() // 2
        for i in range(self._count):
            cx = x + i * (dot_r * 2 + gap) + dot_r
            if i == self._current:
                p.setBrush(QColor(t.accent))
                p.setPen(Qt.PenStyle.NoPen)
                p.drawEllipse(cx - dot_r, cy - dot_r, dot_r * 2, dot_r * 2)
            else:
                p.setBrush(QColor(t.border))
                p.setPen(Qt.PenStyle.NoPen)
                p.drawEllipse(cx - dot_r + 1, cy - dot_r + 1, (dot_r - 1) * 2, (dot_r - 1) * 2)
