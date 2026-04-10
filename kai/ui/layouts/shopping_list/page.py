from kai.ui.layouts.shopping_list.picker import ShoppingListPickerMixin
from kai.ui.layouts.shopping_list.cart import ShoppingListCartMixin

from PySide6.QtWidgets import QWidget, QGridLayout, QStyle, QStyleOption
from PySide6.QtGui import QPainter


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

        self.layout = QGridLayout()
        self.layout.setContentsMargins(8, 8, 8, 8)
        self.layout.setSpacing(8)
        self.layout.setColumnStretch(0, 2)
        self.layout.setColumnStretch(1, 3)
        self.setLayout(self.layout)

        self._build_left_panel()
        self._build_right_panel()
        self.connections()
        self._load_draft()

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
        self.show_saved_btn.clicked.connect(self._show_saved_lists)
        self.back_to_recipes_btn.clicked.connect(self._show_recipes)
        self.show_items_btn.clicked.connect(self._show_item_picker)
        self.back_to_recipes_btn2.clicked.connect(self._show_recipes)
        self.item_search.textChanged.connect(self._filter_item_rows)
        self.state.new_recipes.connect(self._refresh_recipe_cards)
        self.state.new_items.connect(self._refresh_item_rows)
        self.recipe_search.textChanged.connect(self._filter_recipe_cards)
