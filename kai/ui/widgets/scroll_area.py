from kai.ui import theme

from PySide6.QtWidgets import QScrollArea, QFrame
from PySide6.QtCore import Qt


class ThemedScrollArea(QScrollArea):
    """Reusable scroll area with consistent Kai defaults and scrollbar styling."""

    def __init__(
        self,
        parent=None,
        *,
        show_horizontal_bar: bool = False,
        scrollbar_width: int = 6,
    ):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
            if show_horizontal_bar
            else Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.setStyleSheet(theme.scrollbar_css(scrollbar_width))
