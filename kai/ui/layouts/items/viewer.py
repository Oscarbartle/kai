from __future__ import annotations
from datetime import datetime, timedelta

from kai.objects.item import Item
from kai.ui.widgets.item_details import ItemDetails
from kai.ui.widgets.item_view import ItemView
from kai.ui import theme
from kai.ui.refresh_worker import run_refresh, progress as refresh_progress

from PySide6.QtWidgets import (
    QLabel, QWidget, QVBoxLayout, QHBoxLayout, QStyle, QStyleOption,
    QScrollArea, QPushButton, QComboBox, QLineEdit, QStackedWidget,
)
from PySide6.QtGui import QPainter, QCursor
from PySide6.QtCore import Qt

_STALE_AFTER = timedelta(days=7)

# Sort keys read attributes already on the ItemDetails card — no data refetch.
# (label, card_key_fn, reverse)
_SORTS: list[tuple[str, callable, bool]] = [
    ("A–Z",            lambda c: (c.name or "").lower(),                                       False),
    ("Z–A",            lambda c: (c.name or "").lower(),                                       True),
    ("Cheapest",       lambda c: c.current_price if c.current_price else 9999.0,               False),
    ("Most Expensive", lambda c: c.current_price or 0.0,                                       True),
    ("Best Deal",      lambda c: ((c.original_price - c.current_price) / c.original_price)
                                  if c.original_price else 0.0,                                True),
    ("On Special",     lambda c: c.is_special,                                                 True),
]
_SORT_LABELS = [s[0] for s in _SORTS]


class ItemsViewer(QWidget):
    def __init__(self, state):
        super().__init__()

        self.state = state
        self.active_tag = "All"
        self.active_sort = 0  # index into _SORTS

        self.layout = QVBoxLayout()
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)
        self.setLayout(self.layout)

        self.stack = QStackedWidget()
        self.layout.addWidget(self.stack)

        # page 0: item list
        self.list_page = QWidget()
        self._list_layout = QVBoxLayout(self.list_page)
        self._list_layout.setContentsMargins(12, 12, 12, 12)
        self._list_layout.setSpacing(8)

        self._view_widget = None

        self.create_widgets()
        self.add_layouts()

        self.stack.addWidget(self.list_page)
        self.stack.setCurrentIndex(0)

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
        header.setSpacing(8)
        header.addWidget(self.items_label)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search items…")
        self.search_input.setFixedHeight(34)
        self.search_input.setClearButtonEnabled(True)
        self.search_input.textChanged.connect(self._filter_items)
        header.addWidget(self.search_input, 1)

        self.sort_combo = QComboBox()
        self.sort_combo.addItems(_SORT_LABELS)
        self.sort_combo.setFixedHeight(34)
        self.sort_combo.setToolTip("Sort items")
        self.sort_combo.currentIndexChanged.connect(self._on_sort_changed)
        header.addWidget(self.sort_combo)

        self.refresh_all_button = QPushButton("↻ Refresh All")
        self.refresh_all_button.setFixedHeight(34)
        self.refresh_all_button.setProperty("btn", "secondary")
        self.refresh_all_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.refresh_all_button.setToolTip("Refresh prices for stale items (>7 days old)")
        self.refresh_all_button.clicked.connect(self._on_refresh_all)
        header.addWidget(self.refresh_all_button)

        self.add_button = QPushButton("+ Add Item")
        self.add_button.setFixedHeight(34)
        self.add_button.setProperty("btn", "primary")
        self.add_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.add_button.setToolTip("Add new item")
        header.addWidget(self.add_button)

        self._list_layout.addLayout(header)
        self._list_layout.addWidget(self.scroll_area)

    def connections(self):
        self.state.new_items.connect(self.reload_items)
        self.state.tag_selected.connect(self.on_tag_selected)
        self.state.price_mode_changed.connect(self.reload_items)

    def on_tag_selected(self, tag: str):
        self.active_tag = tag
        self.reload_items()

    def _filter_items(self, text: str = ""):
        q = text.lower().strip()
        for i in range(self.scroll_layout.count()):
            w = self.scroll_layout.itemAt(i).widget()
            if w is None:
                continue
            name = getattr(w, "name", "") or ""
            tags = getattr(w, "tags", []) or []
            match = (not q
                     or q in name.lower()
                     or any(q in t.lower() for t in tags))
            w.setVisible(match)

    def _on_sort_changed(self, index: int):
        self.active_sort = index
        # reorder existing widgets — no need to rebuild any cards
        cards = []
        while self.scroll_layout.count():
            item = self.scroll_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                cards.append(w)
        self._sort_and_layout_cards(cards)
        if hasattr(self, "search_input"):
            self._filter_items(self.search_input.text())

    def _sort_and_layout_cards(self, cards):
        _, key_fn, reverse = _SORTS[self.active_sort]
        cards.sort(key=key_fn, reverse=reverse)
        for c in cards:
            self.scroll_layout.addWidget(c)
        self.scroll_layout.addStretch()

    def _on_refresh_all(self):
        cutoff = datetime.now() - _STALE_AFTER
        stale = []
        for doc in Item().io.all().values():
            try:
                updated = datetime.fromisoformat(doc.get("date_updated") or "")
                if updated < cutoff:
                    stale.append(doc["name"])
            except (ValueError, TypeError):
                stale.append(doc["name"])

        if not stale:
            self.refresh_all_button.setToolTip("All items are up to date")
            return

        self.refresh_all_button.setToolTip(f"Refreshing {len(stale)} stale items…")
        run_refresh(
            stale,
            on_done=self.state.items_updated,
            button=self.refresh_all_button,
            delay=2.0,
        )

    def reload_items(self):
        while self.scroll_layout.count():
            child = self.scroll_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        item_obj = Item()
        cards = []
        for item_id, doc in item_obj.io.all().items():
            name = doc.get("name")
            if not name:
                continue
            if self.active_tag != "All" and self.active_tag not in (doc.get("tags") or []):
                continue
            card = ItemDetails(name, self.state, doc=doc, item_id=item_id)
            card.item_clicked.connect(self._open_item)
            cards.append(card)

        self._sort_and_layout_cards(cards)
        if hasattr(self, "search_input"):
            self._filter_items(self.search_input.text())

    def _open_item(self, item_name: str):
        if self._view_widget:
            self.stack.removeWidget(self._view_widget)
            self._view_widget.deleteLater()

        view = ItemView(item_name)
        view.back_requested.connect(self._close_item)
        view.data_refreshed.connect(self.state.items_updated)
        self._view_widget = view
        self.stack.addWidget(view)
        self.stack.setCurrentWidget(view)

    def _close_item(self):
        if self._view_widget:
            self.stack.removeWidget(self._view_widget)
            self._view_widget.deleteLater()
            self._view_widget = None
        self.stack.setCurrentIndex(0)
