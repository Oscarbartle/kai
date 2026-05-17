from kai.ui.layouts.shopping_list.picker import ShoppingListPickerMixin
from kai.ui.layouts.shopping_list.cart import ShoppingListCartMixin

from PySide6.QtWidgets import QWidget, QHBoxLayout, QSplitter, QStyle, QStyleOption
from PySide6.QtGui import QPainter
from PySide6.QtCore import Qt, QTimer


class ShoppingListPage(ShoppingListPickerMixin, ShoppingListCartMixin, QWidget):
    def __init__(self, state):
        super().__init__()

        self.state = state
        self.current_list_id = None
        self.recipe_entries = []
        self.extra_items = []
        self.preview_items = []
        self.lt_items = []
        self.lt_have = {}

        outer = QHBoxLayout()
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(0)
        self.setLayout(outer)

        self.h_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.h_splitter.setChildrenCollapsible(False)
        self.h_splitter.setHandleWidth(6)
        outer.addWidget(self.h_splitter)

        self._build_left_panel()
        self._build_right_panel()
        self.connections()
        self._load_draft()
        QTimer.singleShot(0, lambda: self.h_splitter.setSizes([380, 820]))

    def paintEvent(self, event):
        opt = QStyleOption()
        opt.initFrom(self)
        p = QPainter(self)
        self.style().drawPrimitive(QStyle.PE_Widget, opt, p, self)

    def connections(self):
        self.export_button.clicked.connect(self._on_export)
        self.links_button.clicked.connect(self._on_links)
        self.clear_button.clicked.connect(self._on_clear_list)
        self.save_button.clicked.connect(self._on_save)
        self.refresh_button.clicked.connect(self._on_refresh)
        self.item_search.textChanged.connect(self._filter_item_rows)
        self.recipe_search.textChanged.connect(self._filter_recipe_cards)
        self.state.new_recipes.connect(self._refresh_recipe_cards)
        self.state.new_items.connect(self._refresh_item_rows)
