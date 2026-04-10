from kai.ui import theme

from PySide6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QStyle, QStyleOption, QSplitter, QSplitterHandle
from PySide6.QtGui import QPainter, QColor, QCursor
from PySide6.QtCore import Qt, QRect


class _SplitterHandle(QSplitterHandle):
    def __init__(self, orientation, parent):
        super().__init__(orientation, parent)
        self._hovered = False
        self.setMouseTracking(True)

    def enterEvent(self, event):
        self._hovered = True
        self.update()

    def leaveEvent(self, event):
        self._hovered = False
        self.update()

    def paintEvent(self, event):
        t = theme.theme()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        pill_w, pill_h = 32, 3
        cx = self.width() // 2
        cy = self.height() // 2
        rect = QRect(cx - pill_w // 2, cy - pill_h // 2, pill_w, pill_h)
        p.setPen(Qt.PenStyle.NoPen)
        color = QColor(t.accent) if self._hovered else QColor(t.border)
        p.setBrush(color)
        p.drawRoundedRect(rect, pill_h // 2, pill_h // 2)


class StyledSplitter(QSplitter):
    def createHandle(self):
        return _SplitterHandle(self.orientation(), self)


class CollapsibleSection(QWidget):
    """A section with a clickable header that collapses/expands its content."""

    def __init__(self, title, parent=None, collapsed=False):
        super().__init__(parent)

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.setLayout(layout)

        # header button
        self._collapsed = collapsed
        self._arrow_right = "\u25b6"
        self._arrow_down = "\u25bc"

        self.toggle_btn = QPushButton(f"  {self._arrow_down if not collapsed else self._arrow_right}  {title}")
        self.toggle_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.toggle_btn.setFixedHeight(32)
        self.toggle_btn.setStyleSheet(theme.collapsible_btn_css())
        self.toggle_btn.clicked.connect(self._toggle)
        layout.addWidget(self.toggle_btn)

        # content area
        self.content = QWidget()
        self.content.setStyleSheet("background: transparent;")
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(0, 6, 0, 0)
        self.content_layout.setSpacing(4)
        layout.addWidget(self.content)

        if collapsed:
            self.content.setVisible(False)

        self._title = title

    def _toggle(self):
        self._collapsed = not self._collapsed
        self.content.setVisible(not self._collapsed)
        arrow = self._arrow_right if self._collapsed else self._arrow_down
        self.toggle_btn.setText(f"  {arrow}  {self._title}")

    def paintEvent(self, event):
        opt = QStyleOption()
        opt.initFrom(self)
        p = QPainter(self)
        self.style().drawPrimitive(QStyle.PE_Widget, opt, p, self)
