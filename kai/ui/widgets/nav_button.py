from kai.ui import theme
from kai.ui.tokens import FS_BODY, FW_MEDIUM, RADIUS_SM

from PySide6.QtWidgets import QPushButton
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon, QPixmap, QImage, QColor, QPainter
from PySide6.QtSvg import QSvgRenderer


def _colorize_svg(svg_path: str, color: str, size: int = 18) -> QIcon:
    """Render a 'currentColor' SVG at `size`px tinted to `color`."""
    try:
        with open(svg_path, "r", encoding="utf-8") as f:
            svg_data = f.read().replace("currentColor", color).encode("utf-8")
    except OSError:
        return QIcon()

    renderer = QSvgRenderer(svg_data)
    img = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(Qt.GlobalColor.transparent)
    painter = QPainter(img)
    renderer.render(painter)
    painter.end()

    return QIcon(QPixmap.fromImage(img))


class NavButton(QPushButton):
    def __init__(self, text: str, icon_path: str | None = None, parent=None):
        super().__init__(text, parent)
        self._icon_path = icon_path
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(42)
        self.setCheckable(True)
        self.setIconSize(QSize(18, 18))
        self.toggled.connect(self._refresh_icon)
        self._refresh_icon()
        self.setStyleSheet(self._build_style())

    def _refresh_icon(self, checked: bool | None = None):
        if not self._icon_path:
            return
        t = theme.theme()
        is_on = checked if checked is not None else self.isChecked()
        color = t.accent if is_on else t.text_dim
        self.setIcon(_colorize_svg(self._icon_path, color))

    def _build_style(self):
        t = theme.theme()
        return f"""
            QPushButton {{
                background-color: transparent;
                color: {t.text_dim};
                border: none;
                border-radius: {RADIUS_SM}px;
                padding: 8px 14px;
                text-align: left;
                font-size: {FS_BODY}px;
                font-weight: {FW_MEDIUM};
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

