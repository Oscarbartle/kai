from __future__ import annotations
from urllib.parse import urlparse, parse_qs

from kai.objects.item import Item
from kai.core.backend import get_item
from kai.ui import theme
from kai.ui.widgets.tag_pill import TagChip

from PySide6.QtWidgets import (
    QWidget, QStyle, QStyleOption, QPushButton, QVBoxLayout, QHBoxLayout,
    QLineEdit, QLabel, QCheckBox, QFrame, QDoubleSpinBox,
)
from PySide6.QtGui import QPainter, QCursor
from PySide6.QtCore import Qt


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
        lbl = QLabel(text)
        lbl.setStyleSheet(theme.section_label_css())
        return lbl

    def _divider(self) -> QFrame:
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet(theme.divider_line_css())
        return line

    def create_widgets(self):
        t = theme.theme()

        self.card = QWidget()
        self.card.setObjectName("item_add_card")
        self.card.setStyleSheet(theme.inline_card_css("item_add_card"))
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
        self.item_stock_code.setPlaceholderText("Stock code or Woolworths URL")
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

        self.weight_cb = QCheckBox("Sold by weight (e.g. fresh produce)")
        card_layout.addWidget(self.weight_cb)

        self.weight_row = QWidget()
        weight_row_layout = QHBoxLayout(self.weight_row)
        weight_row_layout.setContentsMargins(0, 0, 0, 0)
        weight_row_layout.setSpacing(8)
        weight_lbl = QLabel("Default weight (kg)")
        weight_lbl.setProperty("role", "dim")
        weight_row_layout.addWidget(weight_lbl)
        self.default_weight_spin = QDoubleSpinBox()
        self.default_weight_spin.setRange(0.1, 50.0)
        self.default_weight_spin.setSingleStep(0.1)
        self.default_weight_spin.setDecimals(2)
        self.default_weight_spin.setValue(0.5)
        self.default_weight_spin.setSuffix(" kg")
        self.default_weight_spin.setFixedHeight(34)
        weight_row_layout.addWidget(self.default_weight_spin)
        weight_row_layout.addStretch()
        self.weight_row.setVisible(False)
        card_layout.addWidget(self.weight_row)
        self.weight_cb.toggled.connect(self.weight_row.setVisible)

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
        doc = get_item().get_item_details(self._edit_name)
        if not doc:
            return
        self.item_name.setText(doc.get("name", ""))
        self.item_stock_code.setText(str(doc.get("stock_code", "")))
        self.item_tags.setText(", ".join(doc.get("tags", []) or []))
        self.long_term_cb.setChecked(doc.get("is_long_term", False))
        sold_by_weight = doc.get("sold_by_weight", False)
        self.weight_cb.setChecked(sold_by_weight)
        self.weight_row.setVisible(sold_by_weight)
        if doc.get("default_weight_kg"):
            self.default_weight_spin.setValue(float(doc["default_weight_kg"]))
        # Disable stock code editing since it drives data fetch
        self.item_stock_code.setReadOnly(True)
        self.item_stock_code.setToolTip("Stock code cannot be changed")

    def _refresh_tag_chips(self):
        while self.tags_flow_layout.count():
            child = self.tags_flow_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        existing_tags = sorted(get_item().get_item_tags())
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
        for w in (self.item_name, self.item_stock_code, self.item_tags):
            w.setStyleSheet(theme.input_css())
        self.long_term_cb.setStyleSheet(theme.checkbox_css())
        self.button.setStyleSheet(theme.button_css("primary"))

        self.layout.addWidget(self.card, 1)
        self.layout.addWidget(self.status_label)
        self.layout.addWidget(self.button)

    def connections(self):
        self.button.clicked.connect(self.on_add_item)

    @staticmethod
    def _parse_stock_code(text: str) -> str:
        text = text.strip()
        if not text:
            return text
        try:
            parsed = urlparse(text)
            if parsed.scheme in ("http", "https") and parsed.netloc:
                qs = parse_qs(parsed.query)
                return qs.get("stockcode", [text])[0]
        except Exception:
            pass
        return text

    def on_add_item(self):
        name = self.item_name.text().strip()
        stock_code = self._parse_stock_code(self.item_stock_code.text())
        tags = [t.strip() for t in self.item_tags.text().split(",") if t.strip()]

        if not name:
            self.status_label.setStyleSheet(theme.label_css("danger"))
            self.status_label.setText("Please enter an item name")
            return

        sold_by_weight = self.weight_cb.isChecked()
        default_weight_kg = round(self.default_weight_spin.value(), 2) if sold_by_weight else None

        if self._edit_name:
            i = get_item()
            if name != self._edit_name:
                i.update(self._edit_name, "name", name)
            i.update(name, "tags", tags)
            i.update(name, "is_long_term", self.long_term_cb.isChecked())
            i.update(name, "sold_by_weight", sold_by_weight)
            i.update(name, "default_weight_kg", default_weight_kg)
        else:
            get_item().create(name, stock_code, tags,
                              sold_by_weight=sold_by_weight,
                              default_weight_kg=default_weight_kg)
            if self.long_term_cb.isChecked():
                get_item().update(name, "is_long_term", True)

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