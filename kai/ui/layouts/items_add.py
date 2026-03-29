from kai.objects.item import Item
from kai.ui import theme

from PySide6.QtWidgets import (
    QWidget, QStyle, QStyleOption, QPushButton, QVBoxLayout, QHBoxLayout,
    QLineEdit, QLabel, QCheckBox
)
from PySide6.QtGui import QPainter, QCursor
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


class ItemsAdd(QWidget):
    def __init__(self, state, edit_item=None):
        super().__init__()

        self.state = state
        self._edit_name = edit_item  # item name to edit, or None for new

        self.layout = QVBoxLayout()
        self.layout.setContentsMargins(24, 20, 24, 20)
        self.layout.setSpacing(16)
        self.setLayout(self.layout)

        self.create_widgets()
        self.add_layouts()
        self.connections()

        if self._edit_name:
            self._populate_edit_data()

    def paintEvent(self, event):
        opt = QStyleOption()
        opt.initFrom(self)
        p = QPainter(self)
        self.style().drawPrimitive(QStyle.PE_Widget, opt, p, self)

    def create_widgets(self):
        # --- name field --- #
        self.item_name_label = QLabel("Name")
        self.item_name_label.setProperty("role", "dim")
        self.item_name = QLineEdit()
        self.item_name.setPlaceholderText("e.g. Peanut Butter")

        # --- stock code field --- #
        self.item_stock_code_label = QLabel("Stock Code")
        self.item_stock_code_label.setProperty("role", "dim")
        self.item_stock_code = QLineEdit()
        self.item_stock_code.setPlaceholderText("Woolworths product code")

        # --- tags field --- #
        self.item_tags_label = QLabel("Tags")
        self.item_tags_label.setProperty("role", "dim")
        self.item_tags = QLineEdit()
        self.item_tags.setPlaceholderText("Comma-separated, e.g. Produce, Dairy")

        # --- existing tags section --- #
        self.existing_tags_label = QLabel("Quick add")
        self.existing_tags_label.setProperty("role", "faint")

        self.tags_flow_widget = QWidget()
        self.tags_flow_layout = QHBoxLayout(self.tags_flow_widget)
        self.tags_flow_layout.setContentsMargins(0, 0, 0, 0)
        self.tags_flow_layout.setSpacing(6)
        self.tags_flow_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self._refresh_tag_chips()

        # --- long-term checkbox --- #
        self.long_term_cb = QCheckBox("Long-term item")

        # --- submit button --- #
        self.button = QPushButton("Save Changes" if self._edit_name else "Add Item")
        self.button.setProperty("btn", "primary")
        self.button.setFixedHeight(38)

        # --- status label --- #
        self.status_label = QLabel("")
        self.status_label.setProperty("role", "faint")

    def _populate_edit_data(self):
        doc = Item().get_item_details(self._edit_name)
        if not doc:
            return
        self.item_name.setText(doc.get("name", ""))
        self.item_stock_code.setText(str(doc.get("stock_code", "")))
        self.item_tags.setText(", ".join(doc.get("tags", []) or []))
        self.long_term_cb.setChecked(doc.get("is_long_term", False))
        # Disable stock code editing since it drives data fetch
        self.item_stock_code.setReadOnly(True)
        self.item_stock_code.setToolTip("Stock code cannot be changed")

    def _refresh_tag_chips(self):
        while self.tags_flow_layout.count():
            child = self.tags_flow_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        existing_tags = sorted(Item().get_item_tags())
        for tag in existing_tags:
            if tag and tag.strip():
                chip = TagChip(tag.strip(), self._on_tag_chip_clicked)
                self.tags_flow_layout.addWidget(chip)

        if not existing_tags:
            empty_label = QLabel("No tags yet")
            empty_label.setProperty("role", "faint")
            self.tags_flow_layout.addWidget(empty_label)

    def _on_tag_chip_clicked(self, tag_name):
        current = self.item_tags.text().strip()
        existing = [t.strip() for t in current.split(",") if t.strip()]
        if tag_name not in existing:
            existing.append(tag_name)
            self.item_tags.setText(", ".join(existing))

    def add_layouts(self):
        self.layout.addWidget(self.item_name_label)
        self.layout.addWidget(self.item_name)
        self.layout.addWidget(self.item_stock_code_label)
        self.layout.addWidget(self.item_stock_code)
        self.layout.addWidget(self.item_tags_label)
        self.layout.addWidget(self.item_tags)
        self.layout.addWidget(self.existing_tags_label)
        self.layout.addWidget(self.tags_flow_widget)
        self.layout.addWidget(self.long_term_cb)
        self.layout.addStretch()
        self.layout.addWidget(self.status_label)
        self.layout.addWidget(self.button)

    def connections(self):
        self.button.clicked.connect(self.on_add_item)

    def on_add_item(self):
        name = self.item_name.text().strip()
        stock_code = self.item_stock_code.text().strip()
        tags = [t.strip() for t in self.item_tags.text().split(",") if t.strip()]

        if not name:
            self.status_label.setStyleSheet(theme.label_css("danger"))
            self.status_label.setText("Please enter an item name")
            return

        if self._edit_name:
            i = Item()
            if name != self._edit_name:
                i.update(self._edit_name, "name", name)
            i.update(name, "tags", tags)
            i.update(name, "is_long_term", self.long_term_cb.isChecked())
        else:
            Item().create(name, stock_code, tags)
            if self.long_term_cb.isChecked():
                Item().update(name, "is_long_term", True)

        self.state.items_updated()

        # close parent dialog if present
        parent = self.parent()
        while parent:
            if hasattr(parent, 'accept'):
                parent.accept()
                break
            parent = parent.parent()

        self.status_label.setStyleSheet(theme.label_css("success"))
        self.status_label.setText(f"\u2713 {name} added")

        self.item_name.clear()
        self.item_stock_code.clear()
        self.item_tags.clear()
        self.long_term_cb.setChecked(False)
        self._refresh_tag_chips()