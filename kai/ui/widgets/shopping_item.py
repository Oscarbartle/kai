from kai.objects.item import Item
from kai.ui import theme
from kai.ui.refresh_worker import run_refresh

from PySide6.QtWidgets import QLabel, QWidget, QHBoxLayout, QCheckBox, QPushButton, QStyle, QStyleOption
from PySide6.QtGui import QPainter
from PySide6.QtCore import Qt

class ShoppingItem(QWidget):
    def __init__(self, item_data: dict, on_toggle=None):
        super().__init__()

        self.item_data = item_data
        self.on_toggle = on_toggle
        self.setObjectName("shopping_item")
        self.setMinimumHeight(36)
        self.setMaximumHeight(36)

        self.set_stylesheet()

        self.layout = QHBoxLayout()
        self.layout.setContentsMargins(10, 4, 10, 4)
        self.layout.setSpacing(8)
        self.setLayout(self.layout)

        self.add_widgets()

    def set_stylesheet(self):
        t = theme.theme()
        self.setStyleSheet(f"""
            QWidget#shopping_item {{
                background-color: {t.card};
                border-radius: 6px;
                border: 1px solid {t.border};
            }}
        """)

    def paintEvent(self, event):
        opt = QStyleOption()
        opt.initFrom(self)
        p = QPainter(self)
        self.style().drawPrimitive(QStyle.PE_Widget, opt, p, self)

    def add_widgets(self):
        t = theme.theme()

        self.checkbox = QCheckBox()
        self.checkbox.setChecked(self.item_data.get("purchased", False))
        self.checkbox.setStyleSheet(theme.checkbox_css())
        self.checkbox.stateChanged.connect(self._on_checked)
        self.layout.addWidget(self.checkbox)

        name = self.item_data.get("item_name", "?")
        purchased = self.item_data.get("purchased", False)
        style = f"text-decoration: line-through; color: {t.text_faint};" if purchased else f"color: {t.text};"
        self.name_label = QLabel(f"<b>{name}</b>")
        self.name_label.setStyleSheet(style)
        self.layout.addWidget(self.name_label, 1)

        # tag pills
        tags = self.item_data.get("tags", [])
        for tag in tags:
            pill = QLabel(tag)
            pill.setStyleSheet(f"""
                background-color: {t.surface};
                color: {t.text_dim};
                border: 1px solid {t.border};
                border-radius: 8px;
                padding: 1px 6px;
                font-size: 9px;
            """)
            self.layout.addWidget(pill)

        # units to buy
        units = self.item_data.get("units_needed", 1)
        if units and units > 1:
            units_label = QLabel(f"x{units}")
            units_label.setStyleSheet(f"color: {t.text}; font-size: 12px; font-weight: bold;")
            self.layout.addWidget(units_label)

        # amount needed (e.g. "400g", "1.2kg")
        amount = self.item_data.get("amount")
        amount_unit = self.item_data.get("amount_unit", "")
        if amount and amount_unit and amount_unit != "ea":
            amt = int(amount) if amount == int(amount) else amount
            amount_label = QLabel(f"{amt}{amount_unit}")
            amount_label.setStyleSheet(f"color: {t.text_dim}; font-size: 11px;")
            self.layout.addWidget(amount_label)

        price = self.item_data.get("price")
        if price:
            price_label = QLabel(f"${price}")
            price_label.setStyleSheet(f"color: {t.accent}; font-size: 12px;")
            self.layout.addWidget(price_label)

        self.refresh_button = QPushButton("\u21bb")
        self.refresh_button.setFixedSize(22, 22)
        self.refresh_button.setToolTip(f"Refresh {name}")
        self.refresh_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.refresh_button.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {t.text_faint};
                border: none; font-size: 13px; border-radius: 4px;
            }}
            QPushButton:hover {{ background: {t.accent}22; color: {t.accent}; }}
        """)
        self.refresh_button.clicked.connect(self._on_refresh)
        self.layout.addWidget(self.refresh_button)

    def _on_checked(self, checked):
        t = theme.theme()
        purchased = bool(checked)
        style = f"text-decoration: line-through; color: {t.text_faint};" if purchased else f"color: {t.text};"
        self.name_label.setStyleSheet(style)
        if self.on_toggle:
            self.on_toggle(self.item_data.get("item_name"), purchased)

    def _on_refresh(self):
        name = self.item_data.get("item_name")
        if name:
            run_refresh([name], parent=self)
