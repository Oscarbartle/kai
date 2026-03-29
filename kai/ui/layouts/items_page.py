from kai.ui.layouts.items_add import ItemsAdd
from kai.ui.layouts.tags import Tags
from kai.ui.layouts.items_viewer import ItemsViewer
from kai.ui import theme

from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QGridLayout,
    QStyle, QStyleOption, QDialog
)
from PySide6.QtGui import QPainter


class ItemsPage(QWidget):
    def __init__(self, state):
        super().__init__()

        self.state = state

        self.layout = QGridLayout()
        self.layout.setContentsMargins(8, 8, 8, 8)
        self.layout.setSpacing(8)
        self.layout.setColumnStretch(0, 1)
        self.layout.setColumnStretch(1, 3)
        self.setLayout(self.layout)

        self.add_widgets()

    def paintEvent(self, event):
        opt = QStyleOption()
        opt.initFrom(self)
        p = QPainter(self)
        self.style().drawPrimitive(QStyle.PE_Widget, opt, p, self)

    def add_widgets(self):
        self.items_existing = Tags(self.state)
        self.items_existing.setObjectName("page_panel")
        self.layout.addWidget(self.items_existing, 0, 0)

        self.items_details = ItemsViewer(self.state)
        self.items_details.setObjectName("page_panel")
        self.items_details.add_button.clicked.connect(self._open_add_dialog)
        self.layout.addWidget(self.items_details, 0, 1)

    def _open_add_dialog(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("New Item")
        dialog.setMinimumSize(440, 460)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(0, 0, 0, 0)

        items_add = ItemsAdd(self.state)
        layout.addWidget(items_add)

        dialog.exec()
