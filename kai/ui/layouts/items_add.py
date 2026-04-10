from kai.objects.item import Item
from kai.ui import theme

from PySide6.QtWidgets import (
    QWidget, QStyle, QStyleOption, QPushButton, QVBoxLayout, QHBoxLayout,
    QLineEdit, QLabel, QCheckBox, QFrame
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

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(20, 18, 20, 18)
        self.layout.setSpacing(14)

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

    def _section_label(self, text: str) -> QLabel:
        t = theme.theme()
        lbl = QLabel(text)
        lbl.setStyleSheet(
            f"color: {t.text_dim}; font-size: 10px; font-weight: 700; "
            f"letter-spacing: 0.8px; text-transform: uppercase;"
        )
        return lbl

    def _divider(self) -> QFrame:
        t = theme.theme()
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet(f"background: {t.border}; border: none; max-height: 1px;")
        return line

    def create_widgets(self):
        t = theme.theme()

        self.card = QWidget()
        self.card.setObjectName("item_add_card")
        self.card.setStyleSheet(f"""
            QWidget#item_add_card {{
                background: {t.card};
                border: 1px solid {t.border};
                border-radius: 10px;
            }}
        """)
        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(16, 16, 16, 16)
        card_layout.setSpacing(12)

        card_layout.addWidget(self._section_label("Item Details"))

        name_lbl = QLabel("Name")
        name_lbl.setProperty("role", "dim")
        card_layout.addWidget(name_lbl)
        self.item_name = QLineEdit()
        self.item_name.setPlaceholderText("e.g. Peanut Butter")
        self.item_name.setFixedHeight(34)
        card_layout.addWidget(self.item_name)

        code_lbl = QLabel("Stock Code")
        code_lbl.setProperty("role", "dim")
        card_layout.addWidget(code_lbl)
        self.item_stock_code = QLineEdit()
        self.item_stock_code.setPlaceholderText("Woolworths product code")
        self.item_stock_code.setFixedHeight(34)
        card_layout.addWidget(self.item_stock_code)

        tags_lbl = QLabel("Tags")
        tags_lbl.setProperty("role", "dim")
        card_layout.addWidget(tags_lbl)
        self.item_tags = QLineEdit()
        self.item_tags.setPlaceholderText("e.g. Produce, Dairy")
        self.item_tags.setFixedHeight(34)
        card_layout.addWidget(self.item_tags)

        card_layout.addWidget(self._divider())

        card_layout.addWidget(self._section_label("Quick Add Tag"))

        self.tags_flow_widget = QWidget()
        self.tags_flow_layout = QHBoxLayout(self.tags_flow_widget)
        self.tags_flow_layout.setContentsMargins(0, 0, 0, 0)
        self.tags_flow_layout.setSpacing(6)
        self.tags_flow_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self._refresh_tag_chips()
        card_layout.addWidget(self.tags_flow_widget)

        card_layout.addWidget(self._divider())

        self.long_term_cb = QCheckBox("Long-term item")
        card_layout.addWidget(self.long_term_cb)

        card_layout.addStretch()

        # status label lives outside the card
        self.status_label = QLabel("")
        self.status_label.setProperty("role", "faint")

        # save button
        self.button = QPushButton("Save Changes" if self._edit_name else "Add Item")
        self.button.setProperty("btn", "primary")
        self.button.setFixedHeight(40)
        self.button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

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
        input_style = theme.input_css()
        cb_style = theme.checkbox_css()

        for w in (self.item_name, self.item_stock_code, self.item_tags):
            w.setStyleSheet(input_style)
        self.long_term_cb.setStyleSheet(cb_style)
        self.button.setStyleSheet(theme.button_css(primary=True))

        self.layout.addWidget(self.card, 1)
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