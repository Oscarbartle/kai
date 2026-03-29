from kai.objects.item import Item
from kai.utils.format_date import format_date
from kai.ui import theme
from kai.core import settings as app_settings

from datetime import datetime, timedelta
from PySide6.QtWidgets import QLabel, QWidget, QGridLayout, QStyle, QStyleOption, QHBoxLayout, QCheckBox, QPushButton, QMenu, QDialog, QVBoxLayout
from PySide6.QtGui import QPainter, QAction
from PySide6.QtCore import Qt

class ItemDetails(QWidget):
    def __init__(self, item_name, state=None):
        super().__init__()

        self.state = state
        doc = Item().get_item_details(item_name)

        if doc is None:
            print(f"Item {item_name} not found")
            return

        self.name = doc["name"]
        self.id = self._get_id_by_name(item_name)

        self.stock_code = doc["stock_code"]

        self.current_price = float(doc["online_data"]["Standard Pricing"]["Current Price"])
        self.original_price = float(doc["online_data"]["Standard Pricing"]["Original Price"])

        self.is_special = self.current_price < self.original_price

        self.discount_percentage = doc["online_data"]["Standard Pricing"]["Discount Percentage"]

        self.price_per_unit = float(doc["online_data"]["Unit Economics"]["Price per Kg/Unit"])
        self.measure = doc["online_data"]["Unit Economics"]["Measure"]

        # determine display based on price mode setting
        price_mode = app_settings.get("price_display_mode")
        has_weight = self.price_per_unit is not None and self.measure
        if price_mode == "per_weight" and has_weight:
            measure_lower = self.measure.lower()
            if "kg" in measure_lower:
                self.display_price = round(self.price_per_unit / 10, 2)
                self.display_suffix = "/100g"
            elif "100g" in measure_lower or "100ml" in measure_lower:
                self.display_price = round(self.price_per_unit, 2)
                self.display_suffix = f"/{self.measure}"
            elif "l" in measure_lower:
                self.display_price = round(self.price_per_unit / 10, 2)
                self.display_suffix = "/100ml"
            else:
                self.display_price = round(self.price_per_unit, 2)
                self.display_suffix = f"/{self.measure}"
            self.secondary_price = self.current_price
            self.secondary_suffix = "ea"
        else:
            self.display_price = self.current_price
            self.display_suffix = ""
            self.secondary_price = self.price_per_unit
            self.secondary_suffix = f"/{self.measure}" if self.measure else ""

        self.total_savings = doc["online_data"]["Promotional Details"]["Total Savings"]
        self.promo_start = doc["online_data"]["Promotional Details"]["Promo Start"]
        self.promo_end = doc["online_data"]["Promotional Details"]["Promo End"]

        self.tags = doc["tags"]
        self.tags.sort()

        self.date_added = doc["date_added"]
        self.date_updated = doc.get("date_updated", self.date_added)
        self.is_long_term = doc.get("is_long_term", False)

        self.setObjectName("item_card")
        self.setMinimumHeight(62)
        self.setMaximumHeight(62)

        self.set_stylesheet()

        self.layouts()
        self.add_widgets()
        self.add_layouts()

    def _get_id_by_name(self, name):
        return Item()._get_id_by_name(name)

    def set_stylesheet(self):
        t = theme.theme()
        border_color = t.success if self.is_special else t.border
        self.setStyleSheet(f"""
            QWidget#item_card {{
                background-color: {t.card};
                border-radius: 8px;
                border: 2px solid {border_color};
            }}
        """)

    def paintEvent(self, event):
        opt = QStyleOption()
        opt.initFrom(self)
        p = QPainter(self)
        self.style().drawPrimitive(QStyle.PE_Widget, opt, p, self)

    def layouts(self):
        self.grid_layout = QGridLayout()
        self.grid_layout.setContentsMargins(10, 6, 10, 6)
        self.grid_layout.setSpacing(5)
        self.setLayout(self.grid_layout)

    def add_widgets(self):
        t = theme.theme()

        self.items_label = QLabel(f"<b>{self.name}</b>")
        self.items_label.setStyleSheet(f"color: {t.text}; font-size: 13px;")

        self.tags_label = QLabel(f"{', '.join(self.tags)}")
        self.tags_label.setStyleSheet(f"color: {t.text_faint}; font-size: 11px; padding-left: 4px;")

        price_color = t.success if self.is_special else t.accent
        self.price_label = QLabel(f"<b>${self.display_price:.2f}{self.display_suffix}</b>")
        self.price_label.setStyleSheet(f"color: {price_color}; font-size: 14px;")

        if self.is_special:
            promo_start_text = format_date(self.promo_start) if self.promo_start else "N/A"
            promo_end_text = format_date(self.promo_end) if self.promo_end else "N/A"
            self.price_label.setToolTip(f"On sale: {promo_start_text} → {promo_end_text}")

        # special end date label
        if self.is_special and self.promo_end:
            self.promo_end_label = QLabel(f"ends {format_date(self.promo_end)}")
            self.promo_end_label.setStyleSheet(f"color: {t.success}; font-size: 10px;")
        else:
            self.promo_end_label = None

        # measure label – hide when no meaningful data
        has_measure = self.secondary_price and self.secondary_suffix
        if has_measure:
            self.measure_label = QLabel(f"${self.secondary_price:.2f}{self.secondary_suffix}")
            self.measure_label.setStyleSheet(f"color: {t.text_dim}; font-size: 11px; padding-left: 4px;")
        else:
            self.measure_label = None

        self.date_added_label = QLabel(f"{format_date(self.date_added)}")
        self.date_added_label.setStyleSheet(f"color: {t.text_faint}; font-size: 10px;")
        self.date_added_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        # date_updated with staleness indicator
        try:
            updated_dt = datetime.fromisoformat(self.date_updated)
            is_stale = (datetime.now() - updated_dt) > timedelta(days=7)
        except (ValueError, TypeError):
            is_stale = True
        updated_color = t.danger if is_stale else t.text_faint
        updated_prefix = "⚠ " if is_stale else ""
        self.date_updated_label = QLabel(f"{updated_prefix}{format_date(self.date_updated)}")
        self.date_updated_label.setStyleSheet(f"color: {updated_color}; font-size: 10px;")
        self.date_updated_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.date_updated_label.setToolTip("Last refreshed" + (" — data is over a week old" if is_stale else ""))

        self.stock_code_label = QLabel(f"{self.stock_code}")
        self.stock_code_label.setStyleSheet(f"color: {t.text_faint}; font-size: 10px;")
        self.stock_code_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        self.long_term_cb = QCheckBox("LT")
        self.long_term_cb.setChecked(self.is_long_term)
        self.long_term_cb.setToolTip("Long-term item (excluded from weekly shopping lists)")
        self.long_term_cb.stateChanged.connect(self._on_long_term_toggled)

        self.refresh_button = QPushButton("\u21bb")
        self.refresh_button.setFixedSize(22, 22)
        self.refresh_button.setToolTip("Refresh Woolworths data")
        self.refresh_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.refresh_button.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {t.text_faint};
                border: none; font-size: 14px; font-weight: bold;
                border-radius: 4px;
            }}
            QPushButton:hover {{ background: {t.accent}22; color: {t.accent}; }}
        """)
        self.refresh_button.clicked.connect(self._on_refresh)

        self.delete_button = QPushButton("\u2715")
        self.delete_button.setFixedSize(22, 22)
        self.delete_button.setToolTip("Delete item")
        self.delete_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.delete_button.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {t.text_faint};
                border: none; font-size: 14px; font-weight: bold;
            }}
            QPushButton:hover {{ color: {t.danger}; background: {t.danger}22; border-radius: 4px; }}
        """)
        self.delete_button.clicked.connect(self._on_delete)

        if self.is_special:
            self.original_price_label = QLabel(f"<s>${self.original_price:.2f}</s>")
            self.original_price_label.setStyleSheet(f"color: {t.danger}; font-size: 12px;")

    def add_layouts(self):
        # Row 0: name | tags (stretch) | right_row0: [LT | ↻ | date | spacing | ✕]
        self.grid_layout.addWidget(self.items_label, 0, 0)
        self.grid_layout.addWidget(self.tags_label, 0, 1)
        self.grid_layout.setColumnStretch(1, 1)

        right_row0 = QHBoxLayout()
        right_row0.setContentsMargins(0, 0, 0, 0)
        right_row0.setSpacing(6)
        right_row0.addWidget(self.long_term_cb)
        right_row0.addWidget(self.refresh_button)
        right_row0.addWidget(self.date_updated_label)
        right_row0.addSpacing(8)
        right_row0.addWidget(self.delete_button)
        self.grid_layout.addLayout(right_row0, 0, 2)

        # Row 1: price | measure | right_row1: [promo info if special | stretch | stock_code]
        price_layout = QHBoxLayout()
        price_layout.setContentsMargins(0, 0, 0, 0)
        price_layout.setSpacing(4)
        price_layout.addWidget(self.price_label)
        if self.is_special:
            price_layout.addWidget(self.original_price_label)
        price_layout.addStretch()
        self.grid_layout.addLayout(price_layout, 1, 0)

        if self.measure_label:
            self.grid_layout.addWidget(self.measure_label, 1, 1)

        right_row1 = QHBoxLayout()
        right_row1.setContentsMargins(0, 0, 0, 0)
        right_row1.setSpacing(8)
        if self.promo_end_label:
            right_row1.addWidget(self.promo_end_label)
        right_row1.addStretch()
        right_row1.addWidget(self.stock_code_label)
        self.grid_layout.addLayout(right_row1, 1, 2)

    def _on_long_term_toggled(self, checked):
        Item().update(self.name, "is_long_term", bool(checked))
        if self.state:
            self.state.items_updated()

    def _on_refresh(self):
        Item().refresh_online_data(self.name)
        if self.state:
            self.state.items_updated()

    def _on_delete(self):
        Item().delete(self.name)
        if self.state:
            self.state.items_updated()

    def contextMenuEvent(self, event):
        p = theme._active
        menu = QMenu(self)
        menu.setStyleSheet(
            f"QMenu {{ background:{p.surface}; color:{p.text}; border:1px solid {p.border}; padding:4px; }}"
            f"QMenu::item {{ padding:6px 24px 6px 12px; border-radius:4px; }}"
            f"QMenu::item:selected {{ background:{p.accent}; color:{p.accent_fg}; }}"
        )
        edit_action = QAction("Edit Item", self)
        edit_action.triggered.connect(self._open_edit_dialog)
        menu.addAction(edit_action)
        menu.exec(event.globalPos())

    def _open_edit_dialog(self):
        from kai.ui.layouts.items_add import ItemsAdd

        dialog = QDialog(self.window())
        dialog.setWindowTitle(f"Edit — {self.name}")
        dialog.setMinimumSize(440, 460)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(0, 0, 0, 0)

        form = ItemsAdd(self.state, edit_item=self.name)
        layout.addWidget(form)

        dialog.exec()