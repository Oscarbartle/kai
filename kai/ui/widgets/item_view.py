from __future__ import annotations

from kai.objects.item import Item
from kai.objects.price_history import PriceHistory
from kai.objects.order_history import OrderHistory
from kai.ui import theme
from kai.ui.refresh_worker import run_refresh
from kai.ui.widgets.charts import make_price_chart
from kai.core import settings as app_settings
from kai.ui.tokens import (
    SPACE_SM, SPACE_MD, SPACE_LG,
    RADIUS_MD, BORDER_W,
    H_ICON_BTN,
    FS_BODY, FS_META, FS_TINY,
    FW_BOLD,
)
from kai.utils.format_date import format_date

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QStyle, QStyleOption, QDialog,
)
from PySide6.QtGui import QPainter, QCursor
from PySide6.QtCore import Qt, Signal


class _StatTile(QWidget):
    """Small card for a single stat (label + value)."""

    def __init__(self, label: str, value: str, accent: bool = False, sub: str = ""):
        super().__init__()
        t = theme.theme()
        self.setObjectName("stat_tile")
        self.setStyleSheet(theme.inline_card_css("stat_tile", radius=RADIUS_MD))

        lay = QVBoxLayout(self)
        lay.setContentsMargins(SPACE_MD, SPACE_SM, SPACE_MD, SPACE_SM)
        lay.setSpacing(2)

        lbl = QLabel(label)
        lbl.setStyleSheet(f"color: {t.text_dim}; font-size: {FS_META}px;")
        lay.addWidget(lbl)

        val = QLabel(value)
        color = t.accent if accent else t.text
        val.setStyleSheet(f"color: {color}; font-size: 18px; font-weight: bold;")
        lay.addWidget(val)

        if sub:
            sub_lbl = QLabel(sub)
            sub_lbl.setStyleSheet(f"color: {t.text_faint}; font-size: {FS_TINY}px;")
            lay.addWidget(sub_lbl)

    def paintEvent(self, event):
        opt = QStyleOption()
        opt.initFrom(self)
        p = QPainter(self)
        self.style().drawPrimitive(QStyle.PE_Widget, opt, p, self)


class ItemView(QWidget):
    """Full-page stats view for a single item."""

    back_requested = Signal()
    data_refreshed = Signal()

    def __init__(self, item_name: str):
        super().__init__()

        item_obj = Item()
        self.doc = item_obj.get_item_details(item_name)
        if self.doc is None:
            return

        self.name = self.doc["name"]
        self._item_id = item_obj._get_id_by_name(self.name)
        self._ph = PriceHistory()
        self._window = int(app_settings.get("price_history_window_days") or 30)

        self._build_ui()

    def paintEvent(self, event):
        opt = QStyleOption()
        opt.initFrom(self)
        p = QPainter(self)
        self.style().drawPrimitive(QStyle.PE_Widget, opt, p, self)

    def _build_ui(self):
        t = theme.theme()
        root = QVBoxLayout(self)
        root.setContentsMargins(SPACE_LG, SPACE_LG, SPACE_LG, SPACE_LG)
        root.setSpacing(SPACE_MD)

        # ── header ── #
        header = QHBoxLayout()
        header.setSpacing(SPACE_SM)

        back_btn = QPushButton("←  Back")
        back_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        back_btn.setProperty("btn", "secondary")
        back_btn.setFixedHeight(32)
        back_btn.clicked.connect(self.back_requested.emit)
        header.addWidget(back_btn)

        title = QLabel(f"<b>{self.name}</b>")
        title.setStyleSheet(f"color: {t.text}; font-size: 18px;")
        header.addWidget(title)

        tags = self.doc.get("tags") or []
        if tags:
            tags_lbl = QLabel(", ".join(tags))
            tags_lbl.setStyleSheet(f"color: {t.text_faint}; font-size: {FS_META}px;")
            header.addWidget(tags_lbl)

        header.addStretch()

        refresh_btn = QPushButton("↻ Refresh")
        refresh_btn.setFixedHeight(32)
        refresh_btn.setProperty("btn", "secondary")
        refresh_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        refresh_btn.clicked.connect(self._on_refresh)
        header.addWidget(refresh_btn)
        self._refresh_btn = refresh_btn

        edit_btn = QPushButton("Edit")
        edit_btn.setFixedHeight(32)
        edit_btn.setProperty("btn", "secondary")
        edit_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        edit_btn.clicked.connect(self._on_edit)
        header.addWidget(edit_btn)

        root.addLayout(header)

        # ── special indicator ── #
        sp = (self.doc.get("online_data") or {}).get("Standard Pricing", {})
        cur = sp.get("Current Price")
        orig = sp.get("Original Price")
        is_special = cur is not None and orig is not None and float(cur) < float(orig)

        if is_special:
            pct = round((float(orig) - float(cur)) / float(orig) * 100)
            saving = float(orig) - float(cur)
            special_bar = QLabel(
                f"🏷  On Special  ·  {pct}% off  ·  Save ${saving:.2f}  ·  was ${float(orig):.2f}"
            )
            special_bar.setStyleSheet(
                f"background: {t.success}; color: #0a2e1a;"
                f" border-radius: {RADIUS_MD}px;"
                f" padding: 6px {SPACE_MD}px;"
                f" font-size: {FS_BODY}px; font-weight: bold;"
            )
            root.addWidget(special_bar)

        # ── stat tiles ── #
        cur_str = f"${float(cur):.2f}" if cur is not None else "N/A"

        at_min = self._ph.all_time_min(self._item_id) if self._item_id else None
        at_max = self._ph.all_time_max(self._item_id) if self._item_id else None
        avg = self._ph.avg_in_window(self._item_id, self._window) if self._item_id else None

        oh_entry = OrderHistory().get(self.name)
        order_count = oh_entry.get("count", 0)
        last_ordered = oh_entry.get("last_date", "")

        tiles_row = QHBoxLayout()
        tiles_row.setSpacing(SPACE_SM)
        tiles_row.addWidget(_StatTile("Current", cur_str, accent=True))
        tiles_row.addWidget(_StatTile("All-time Low", f"${at_min:.2f}" if at_min else "—"))
        tiles_row.addWidget(_StatTile("All-time High", f"${at_max:.2f}" if at_max else "—"))
        tiles_row.addWidget(_StatTile(f"Avg ({self._window}d)", f"${avg:.2f}" if avg else "—"))
        order_sub = format_date(last_ordered) if last_ordered else ""
        tiles_row.addWidget(_StatTile(
            "Times Ordered",
            str(order_count) if order_count else "Never",
            sub=f"Last: {order_sub}" if order_sub else "",
        ))
        root.addLayout(tiles_row)

        # ── price chart ── #
        history = self._ph.get(self._item_id) if self._item_id else []
        if history:
            chart_view = make_price_chart(history, title="Price History")
            chart_view.setMinimumHeight(220)
            root.addWidget(chart_view, 2)
        else:
            empty_lbl = QLabel("No price history yet — refresh the item to start tracking.")
            empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty_lbl.setStyleSheet(f"color: {t.text_faint}; font-size: {FS_BODY}px; padding: 32px;")
            root.addWidget(empty_lbl, 2)

        # ── recent specials ── #
        specials = self._ph.recent_specials(self._item_id) if self._item_id else []
        if specials:
            specials_heading = QLabel("Recent Specials")
            specials_heading.setProperty("role", "heading")
            root.addWidget(specials_heading)

            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setMaximumHeight(140)
            content = QWidget()
            content.setStyleSheet("background: transparent;")
            content_lay = QVBoxLayout(content)
            content_lay.setContentsMargins(4, 4, 4, 4)
            content_lay.setSpacing(4)

            for snap in reversed(specials):
                row = QHBoxLayout()
                date_lbl = QLabel(format_date(snap.get("date", "")))
                date_lbl.setStyleSheet(f"color: {t.text_dim}; font-size: {FS_META}px;")
                row.addWidget(date_lbl)

                price_lbl = QLabel(f"${float(snap['current_price']):.2f}")
                price_lbl.setStyleSheet(f"color: {t.success}; font-size: {FS_BODY}px; font-weight: bold;")
                row.addWidget(price_lbl)

                disc = snap.get("discount_pct", "")
                if disc:
                    disc_lbl = QLabel(f"{disc} off")
                    disc_lbl.setStyleSheet(f"color: {t.success}; font-size: {FS_META}px;")
                    row.addWidget(disc_lbl)

                row.addStretch()
                row_widget = QWidget()
                row_widget.setStyleSheet("background: transparent;")
                row_widget.setLayout(row)
                content_lay.addWidget(row_widget)

            content_lay.addStretch()
            scroll.setWidget(content)
            root.addWidget(scroll)

    def _on_refresh(self):
        run_refresh([self.name], on_done=self.data_refreshed.emit, button=self._refresh_btn)

    def _on_edit(self):
        from kai.ui.layouts.items.add import ItemsAdd
        dialog = QDialog(self.window())
        dialog.setWindowTitle(f"Edit — {self.name}")
        dialog.setMinimumSize(440, 460)
        lay = QVBoxLayout(dialog)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(ItemsAdd(None, edit_item=self.name))
        dialog.exec()
