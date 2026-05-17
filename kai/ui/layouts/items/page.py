from kai.ui.layouts.items.add import ItemsAdd
from kai.ui.layouts.tags import Tags
from kai.ui.layouts.items.viewer import ItemsViewer
from kai.ui import theme

from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QSplitter,
    QStyle, QStyleOption, QDialog
)
from PySide6.QtGui import QPainter
from PySide6.QtCore import Qt


class ItemsPage(QWidget):
    def __init__(self, state):
        super().__init__()

        self.state = state

        outer = QHBoxLayout()
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(0)
        self.setLayout(outer)

        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setChildrenCollapsible(False)
        self.splitter.setHandleWidth(6)
        outer.addWidget(self.splitter)

        self.add_widgets()

    def paintEvent(self, event):
        opt = QStyleOption()
        opt.initFrom(self)
        p = QPainter(self)
        self.style().drawPrimitive(QStyle.PE_Widget, opt, p, self)

    def add_widgets(self):
        self.items_existing = Tags(self.state)
        self.items_existing.setObjectName("page_panel")
        self.splitter.addWidget(self.items_existing)

        self.items_details = ItemsViewer(self.state)
        self.items_details.setObjectName("page_panel")
        self.items_details.add_button.clicked.connect(self._open_add_dialog)
        self.splitter.addWidget(self.items_details)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 3)

    def _open_add_dialog(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("New Item")
        dialog.setMinimumSize(440, 460)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(0, 0, 0, 0)

        items_add = ItemsAdd(self.state)
        layout.addWidget(items_add)

        dialog.exec()
