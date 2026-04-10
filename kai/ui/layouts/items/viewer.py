from kai.objects.item import Item
from kai.ui.widgets.item_details import ItemDetails
from kai.ui import theme

from PySide6.QtWidgets import QLabel, QWidget, QVBoxLayout, QHBoxLayout, QStyle, QStyleOption, QScrollArea, QPushButton
from PySide6.QtGui import QPainter, QCursor
from PySide6.QtCore import Qt


class ItemsViewer(QWidget):
    def __init__(self, state):
        super().__init__()

        self.state = state
        self.active_tag = "All"

        self.layout = QVBoxLayout()
        self.layout.setContentsMargins(12, 12, 12, 12)
        self.layout.setSpacing(8)
        self.setLayout(self.layout)

        self.create_widgets()
        self.add_layouts()

    def paintEvent(self, event):
        opt = QStyleOption()
        opt.initFrom(self)
        p = QPainter(self)
        self.style().drawPrimitive(QStyle.PE_Widget, opt, p, self)

    def create_widgets(self):
        self.items_label = QLabel("Items")
        self.items_label.setProperty("role", "heading")

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)

        self.scroll_widget = QWidget()
        self.scroll_widget.setStyleSheet("background: transparent;")
        self.scroll_layout = QVBoxLayout(self.scroll_widget)
        self.scroll_layout.setContentsMargins(2, 2, 2, 2)
        self.scroll_layout.setSpacing(6)

        self.reload_items()
        self.connections()

        self.scroll_layout.addStretch()

        self.scroll_area.setWidget(self.scroll_widget)

    def add_layouts(self):
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.addWidget(self.items_label)
        header.addStretch()

        self.add_button = QPushButton("+ Add Item")
        self.add_button.setFixedHeight(34)
        self.add_button.setProperty("btn", "primary")
        self.add_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.add_button.setToolTip("Add new item")
        header.addWidget(self.add_button)

        self.layout.addLayout(header)
        self.layout.addWidget(self.scroll_area)

    def connections(self):
        self.state.new_items.connect(self.reload_items)
        self.state.tag_selected.connect(self.on_tag_selected)
        self.state.price_mode_changed.connect(self.reload_items)

    def on_tag_selected(self, tag: str):
        self.active_tag = tag
        self.reload_items()

    def reload_items(self):
        while self.scroll_layout.count():
            child = self.scroll_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        item_obj = Item()
        all_data = item_obj.io.all()
        items_data = sorted(
            ((v["name"], k, v) for k, v in all_data.items()),
            key=lambda x: x[0]
        )

        for name, item_id, doc in items_data:
            if self.active_tag != "All" and self.active_tag not in (doc.get("tags") or []):
                continue
            self.scroll_layout.addWidget(ItemDetails(name, self.state, doc=doc))

        self.scroll_layout.addStretch()
