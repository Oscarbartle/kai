from kai.objects.item import Item
from kai.core.backend import get_item, get_price_history
from kai.utils.format_date import format_date
from kai.ui import theme
from kai.ui.refresh_worker import run_refresh
from kai.core import settings as app_settings
from kai.ui.tokens import (
    SPACE_SM, SPACE_MD,
    RADIUS_MD, BORDER_W,
    H_CARD, H_ICON_BTN,
    FS_BODY, FS_META, FS_TINY, FS_HEADING,
    FW_BOLD, FW_MEDIUM,
)

from datetime import datetime, timedelta
from PySide6.QtWidgets import (
    QLabel, QWidget, QGridLayout, QStyle, QStyleOption,
    QHBoxLayout, QCheckBox, QPushButton, QMenu, QDialog, QVBoxLayout
)
from PySide6.QtGui import QPainter, QAction, QDesktopServices
from PySide6.QtCore import Qt, QUrl, Signal

class ItemDetails(QWidget):
    item_clicked = Signal(str)

    def __init__(self, item_name, state=None, doc=None, item_id=None):
        super().__init__()

        self.state = state
        if doc is None:
            doc = get_item().get_item_details(item_name)

        if doc is None:
            print(f"Item {item_name} not found")
            return

        self.name = doc["name"]
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
        self.is_unavailable = doc.get("unavailable", False)
        self.is_out_of_stock = doc.get("out_of_stock", False)

        # price history flags — use the id we were handed when available
        self._item_id = item_id if item_id is not None else get_item()._get_id_by_name(self.name)
        self._is_n_day_low = False
        self._is_all_time_low = False
        self._history_window = int(app_settings.get("price_history_window_days") or 30)
        if self._item_id and not self.is_unavailable and not self.is_out_of_stock:
            # one history fetch, compute both mins locally — avoids two O(snapshots) scans
            history = get_price_history().get(self._item_id)
            if history:
                from datetime import datetime, timedelta
                cutoff = datetime.now() - timedelta(days=self._history_window)
                window_prices = []
                all_prices = []
                for snap in history:
                    p = snap.get("current_price")
                    if p is None:
                        continue
                    p = float(p)
                    all_prices.append(p)
                    try:
                        if datetime.fromisoformat(snap["date"]) >= cutoff:
                            window_prices.append(p)
                    except (ValueError, TypeError):
                        pass
                cur = self.current_price
                if window_prices and cur <= min(window_prices):
                    self._is_n_day_low = True
                if all_prices and cur <= min(all_prices):
                    self._is_all_time_low = True

        self.setObjectName("item_card")
        self.setMinimumHeight(H_CARD)
        self.setMaximumHeight(H_CARD)

        self.set_stylesheet()
        self.layouts()
        self.add_widgets()
        self.add_layouts()

    def _get_id_by_name(self, name):
        return get_item()._get_id_by_name(name)

    def set_stylesheet(self):
        t = theme.theme()
        if self.is_unavailable:
            border_color = t.text_faint
        elif self.is_out_of_stock:
            border_color = t.danger
        elif self.is_special:
            border_color = t.success
        else:
            border_color = t.border
        opacity = "opacity: 0.6;" if (self.is_unavailable or self.is_out_of_stock) else ""
        self.setStyleSheet(f"""
            QWidget#item_card {{
                background-color: {t.card};
                border-radius: {RADIUS_MD}px;
                border: {BORDER_W}px solid {border_color};
                {opacity}
            }}
        """)

    def paintEvent(self, event):
        opt = QStyleOption()
        opt.initFrom(self)
        p = QPainter(self)
        self.style().drawPrimitive(QStyle.PE_Widget, opt, p, self)

    def layouts(self):
        self.grid_layout = QGridLayout()
        self.grid_layout.setContentsMargins(SPACE_MD, SPACE_SM, SPACE_MD, SPACE_SM)
        self.grid_layout.setSpacing(4)
        self.grid_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        self.setLayout(self.grid_layout)

    def add_widgets(self):
        t = theme.theme()

        self.items_label = QLabel(f"<b>{self.name}</b>")
        self.items_label.setStyleSheet(f"color: {t.text}; font-size: {FS_BODY}px;")

        self.tags_label = QLabel(f"{', '.join(self.tags)}")
        self.tags_label.setStyleSheet(
            f"color: {t.text_faint}; font-size: {FS_META}px; padding-left: 4px;"
        )

        # Rich hover tooltip: full pricing + promo dates + stock code + dates
        try:
            updated_dt = datetime.fromisoformat(self.date_updated)
            is_stale = (datetime.now() - updated_dt) > timedelta(days=7)
        except (ValueError, TypeError):
            is_stale = True

        tooltip_lines = []
        tooltip_lines.append(f"${self.current_price:.2f} ea")
        if self.price_per_unit and self.measure:
            tooltip_lines.append(f"${self.price_per_unit:.2f}/{self.measure}")
        if self.is_special:
            tooltip_lines.append(f"Was: ${self.original_price:.2f} ({self.discount_percentage} off)")
            promo_s = format_date(self.promo_start) if self.promo_start else "?"
            promo_e = format_date(self.promo_end) if self.promo_end else "?"
            tooltip_lines.append(f"Sale: {promo_s} → {promo_e}")
        tooltip_lines.append(f"Stock code: {self.stock_code}")
        tooltip_lines.append(f"Added: {format_date(self.date_added)}")
        stale_tag = " (stale)" if is_stale else ""
        tooltip_lines.append(f"Refreshed: {format_date(self.date_updated)}{stale_tag}")
        if self.is_out_of_stock:
            tooltip_lines.append("⚠ Currently out of stock at Woolworths")
        self.setToolTip("\n".join(tooltip_lines))

        if self.is_unavailable:
            price_color = t.text_faint
        elif self.is_special:
            price_color = t.success
        else:
            price_color = t.accent

        self.price_label = QLabel(f"<b>${self.display_price:.2f}{self.display_suffix}</b>")
        self.price_label.setStyleSheet(f"color: {price_color}; font-size: {FS_HEADING}px;")

        # special end date label
        if self.is_unavailable:
            self.unavailable_label = QLabel("Unavailable")
            self.unavailable_label.setStyleSheet(
                f"color: {t.text_faint}; font-size: {FS_META}px; font-style: italic;"
            )
        elif self.is_out_of_stock:
            self.unavailable_label = QLabel("Out of Stock")
            self.unavailable_label.setStyleSheet(
                f"color: {t.danger}; font-size: {FS_META}px; font-style: italic;"
            )
        else:
            self.unavailable_label = None

        if self.is_special and self.promo_end:
            self.promo_end_label = QLabel(f"ends {format_date(self.promo_end)}")
            self.promo_end_label.setStyleSheet(f"color: {t.success}; font-size: {FS_META}px;")
        else:
            self.promo_end_label = None

        has_measure = self.secondary_price and self.secondary_suffix
        if has_measure:
            self.measure_label = QLabel(f"${self.secondary_price:.2f}{self.secondary_suffix}")
            self.measure_label.setStyleSheet(
                f"color: {t.text_dim}; font-size: {FS_META}px; padding-left: 4px;"
            )
        else:
            self.measure_label = None

        # date_updated with staleness indicator
        updated_color = t.danger if is_stale else t.text_faint
        updated_prefix = "⚠ " if is_stale else ""
        self.date_updated_label = QLabel(f"{updated_prefix}{format_date(self.date_updated)}")
        self.date_updated_label.setStyleSheet(
            f"color: {updated_color}; font-size: {FS_META}px;"
        )
        self.date_updated_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        self.long_term_cb = QCheckBox("LT")
        self.long_term_cb.setChecked(self.is_long_term)
        self.long_term_cb.setToolTip("Long-term item (excluded from weekly shopping lists)")
        self.long_term_cb.stateChanged.connect(self._on_long_term_toggled)

        self.refresh_button = QPushButton("↻")
        self.refresh_button.setFixedSize(H_ICON_BTN, H_ICON_BTN)
        self.refresh_button.setToolTip("Refresh Woolworths data")
        self.refresh_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.refresh_button.setStyleSheet(theme.icon_btn_css())
        self.refresh_button.clicked.connect(self._on_refresh)

        self.delete_button = QPushButton("✕")
        self.delete_button.setFixedSize(H_ICON_BTN, H_ICON_BTN)
        self.delete_button.setToolTip("Delete item")
        self.delete_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.delete_button.setStyleSheet(theme.delete_btn_css())
        self.delete_button.clicked.connect(self._on_delete)

        if self.is_special:
            self.original_price_label = QLabel(f"<s>${self.original_price:.2f}</s>")
            self.original_price_label.setStyleSheet(
                f"color: {t.danger}; font-size: {FS_BODY}px;"
            )

        self.all_time_low_badge = None
        self.n_day_low_badge = None
        if self._is_all_time_low:
            badge = QLabel("◆")
            badge.setStyleSheet(
                f"color: {t.success}; font-size: {FS_BODY}px;"
            )
            badge.setToolTip("All-time low — lowest price ever recorded for this item")
            self.all_time_low_badge = badge
        elif self._is_n_day_low:
            badge = QLabel("↓")
            badge.setStyleSheet(
                f"color: {t.success}; font-size: {FS_BODY}px; font-weight: bold;"
            )
            badge.setToolTip(f"{self._history_window}-day low — lowest price in the last {self._history_window} days")
            self.n_day_low_badge = badge

    def add_layouts(self):
        # Row 0: name | tags (stretch) | right_row0: [LT | ↻ | date | ✕]
        self.grid_layout.addWidget(self.items_label, 0, 0)
        self.grid_layout.addWidget(self.tags_label, 0, 1)
        self.grid_layout.setColumnStretch(1, 1)

        right_row0 = QHBoxLayout()
        right_row0.setContentsMargins(0, 0, 0, 0)
        right_row0.setSpacing(4)
        right_row0.addWidget(self.long_term_cb)
        right_row0.addSpacing(SPACE_SM)
        right_row0.addWidget(self.refresh_button)
        right_row0.addWidget(self.date_updated_label)
        right_row0.addSpacing(SPACE_SM)
        right_row0.addWidget(self.delete_button)
        self.grid_layout.addLayout(right_row0, 0, 2)

        # Row 1: price | measure | right_row1: [promo info | stretch]
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
        right_row1.setSpacing(SPACE_SM)
        if self.unavailable_label:
            right_row1.addWidget(self.unavailable_label)
        elif self.promo_end_label:
            right_row1.addWidget(self.promo_end_label)
        if self.all_time_low_badge:
            right_row1.addWidget(self.all_time_low_badge)
        elif self.n_day_low_badge:
            right_row1.addWidget(self.n_day_low_badge)
        right_row1.addStretch()
        self.grid_layout.addLayout(right_row1, 1, 2)

    def mousePressEvent(self, event):
        child = self.childAt(event.position().toPoint())
        if child is None or not isinstance(child, (QPushButton, QCheckBox)):
            self.item_clicked.emit(self.name)
        super().mousePressEvent(event)

    def _on_long_term_toggled(self, checked):
        get_item().update(self.name, "is_long_term", bool(checked))
        if self.state:
            self.state.items_updated()

    def _on_refresh(self):
        callbacks = [self.state.items_updated] if self.state else []
        run_refresh([self.name], on_done=callbacks, button=self.refresh_button)

    def _on_delete(self):
        get_item().delete(self.name)
        if self.state:
            self.state.items_updated()

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        menu.setStyleSheet(theme.context_menu_css())
        edit_action = QAction("Edit Item", self)
        edit_action.triggered.connect(self._open_edit_dialog)
        menu.addAction(edit_action)

        woolworths_action = QAction("Open in Browser", self)
        woolworths_action.triggered.connect(self._open_in_woolworths)
        menu.addAction(woolworths_action)

        menu.exec(event.globalPos())

    def _open_in_woolworths(self):
        url = QUrl(f"https://www.woolworths.co.nz/shop/productdetails?stockcode={self.stock_code}")
        QDesktopServices.openUrl(url)

    def _open_edit_dialog(self):
        from kai.ui.layouts.items.add import ItemsAdd

        dialog = QDialog(self.window())
        dialog.setWindowTitle(f"Edit — {self.name}")
        dialog.setMinimumSize(440, 460)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(0, 0, 0, 0)

        form = ItemsAdd(self.state, edit_item=self.name)
        layout.addWidget(form)

        dialog.exec()
