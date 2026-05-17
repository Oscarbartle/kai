from kai.objects.item import Item
from kai.ui import theme
from kai.ui.refresh_worker import run_refresh
from kai.ui.tokens import (
    SPACE_SM, SPACE_MD,
    RADIUS_SM, BORDER_W,
    H_ROW, H_ICON_BTN,
    FS_BODY, FS_META,
    FW_BOLD,
)

from PySide6.QtWidgets import (
    QLabel, QWidget, QHBoxLayout, QCheckBox, QPushButton, QStyle, QStyleOption
)
from PySide6.QtGui import QPainter
from PySide6.QtCore import Qt

class ShoppingItem(QWidget):
    def __init__(self, item_data: dict, on_toggle=None):
        super().__init__()

        self.item_data = item_data
        self.on_toggle = on_toggle
        self.setObjectName("shopping_item")
        self.setMinimumHeight(H_ROW)
        self.setMaximumHeight(H_ROW)

        self.set_stylesheet()

        self.layout = QHBoxLayout()
        self.layout.setContentsMargins(SPACE_MD, 0, SPACE_MD, 0)
        self.layout.setSpacing(SPACE_SM)
        self.setLayout(self.layout)

        self.add_widgets()

    def set_stylesheet(self):
        t = theme.theme()
        source_manual = bool(self.item_data.get("source_manual"))
        source_recipe = bool(self.item_data.get("source_recipe"))
        if source_manual and not source_recipe:
            self.setStyleSheet(f"""
                QWidget#shopping_item {{
                    background-color: {t.card};
                    border-radius: {RADIUS_SM}px;
                    border: {BORDER_W}px solid {t.border};
                    border-left: 3px solid {t.accent};
                }}
            """)
            return
        self.setStyleSheet(theme.inline_card_css("shopping_item", radius=RADIUS_SM))

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
        style = (
            f"text-decoration: line-through; color: {t.text_faint};"
            if purchased else
            f"color: {t.text}; font-size: {FS_BODY}px;"
        )
        self.name_label = QLabel(f"<b>{name}</b>")
        self.name_label.setStyleSheet(style)
        self.layout.addWidget(self.name_label, 1)

        source_recipe = bool(self.item_data.get("source_recipe"))
        source_manual = bool(self.item_data.get("source_manual"))
        manual_units = int(self.item_data.get("manual_units", 0) or 0)
        is_highlighted = source_manual and not source_recipe

        # All secondary info goes into tooltip — keeps the row clean
        tip_lines = []
        source_recipes = self.item_data.get("source_recipes") or []
        tags = self.item_data.get("tags", [])
        if source_recipes:
            tip_lines.append("From: " + ", ".join(source_recipes))
        elif source_recipe:
            tip_lines.append("From: recipe")
        if source_manual:
            tip_lines.append(f"Manually added ×{manual_units if manual_units > 0 else 1}")
        if tags:
            tip_lines.append("Tags: " + ", ".join(tags))
        price = self.item_data.get("price")
        original = self.item_data.get("original_price")
        if price:
            tip_lines.append(f"Price: ${price}")
        if original and original != price:
            tip_lines.append(f"Was: ${original}")
        if tip_lines:
            self.setToolTip("\n".join(tip_lines))

        if source_manual:
            badge_text = str(manual_units) if manual_units > 0 else "1"
            manual_badge = QLabel(badge_text)
            manual_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            manual_badge.setFixedSize(20, 20)
            manual_badge.setStyleSheet(f"""
                background-color: transparent;
                color: {t.text_dim};
                border: 1px solid {t.border};
                border-radius: 10px;
                font-size: {FS_META}px;
                font-weight: {FW_BOLD};
            """)
            manual_badge.setToolTip(
                f"Individually added ×{manual_units}" if manual_units > 0 else "Individually added"
            )
            self.layout.addWidget(manual_badge)

        # units to buy
        units = self.item_data.get("units_needed", 1)
        if units and units > 1:
            units_label = QLabel(f"x{units}")
            units_label.setStyleSheet(
                f"color: {t.text}; font-size: {FS_BODY}px; font-weight: {FW_BOLD};"
            )
            self.layout.addWidget(units_label)

        # amount needed (e.g. "400g", "1.2kg")
        amount = self.item_data.get("amount")
        amount_unit = self.item_data.get("amount_unit", "")
        if amount and amount_unit and amount_unit != "ea":
            amt = int(amount) if amount == int(amount) else amount
            amount_label = QLabel(f"{amt}{amount_unit}")
            amount_label.setStyleSheet(f"color: {t.text_dim}; font-size: {FS_META}px;")
            self.layout.addWidget(amount_label)

        if price:
            price_label = QLabel(f"${price}")
            price_label.setStyleSheet(f"color: {t.accent}; font-size: {FS_META}px;")
            self.layout.addWidget(price_label)

        self.refresh_button = QPushButton("↻")
        self.refresh_button.setFixedSize(H_ICON_BTN, H_ICON_BTN)
        self.refresh_button.setToolTip(f"Refresh {name}")
        self.refresh_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.refresh_button.setStyleSheet(theme.icon_btn_css())
        self.refresh_button.clicked.connect(self._on_refresh)
        self.refresh_button.setVisible(False)
        self.layout.addWidget(self.refresh_button)

    def enterEvent(self, event):
        self.refresh_button.setVisible(True)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.refresh_button.setVisible(False)
        super().leaveEvent(event)

    def _on_checked(self, checked):
        t = theme.theme()
        purchased = bool(checked)
        style = (
            f"text-decoration: line-through; color: {t.text_faint};"
            if purchased else
            f"color: {t.text}; font-size: {FS_BODY}px;"
        )
        self.name_label.setStyleSheet(style)
        if self.on_toggle:
            self.on_toggle(self.item_data.get("item_name"), purchased)

    def _on_refresh(self):
        name = self.item_data.get("item_name")
        if name:
            run_refresh([name], button=self.refresh_button)
