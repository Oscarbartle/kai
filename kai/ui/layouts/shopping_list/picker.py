from kai.objects.recipe import Recipe
from kai.objects.item import Item
from kai.objects.shopping_list import ShoppingList
from kai.ui import theme
from kai.ui.layouts.shopping_list.cards import RecipePickerCard, SavedListCard

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QStackedWidget,
    QLabel,
    QPushButton,
    QLineEdit,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
)
from PySide6.QtGui import QCursor
from PySide6.QtCore import Qt


class ShoppingListPickerMixin:
    # ── left panel: recipe picker + item picker + saved lists ── #

    def _build_left_panel(self):
        self.left_panel = QWidget()
        self.left_panel.setObjectName("page_panel")
        left_layout = QVBoxLayout(self.left_panel)
        left_layout.setContentsMargins(12, 12, 12, 12)
        left_layout.setSpacing(8)

        self.left_stack = QStackedWidget()

        # --- page 0: recipe picker --- #
        self.picker_page = QWidget()
        picker_layout = QVBoxLayout(self.picker_page)
        picker_layout.setContentsMargins(0, 0, 0, 0)
        picker_layout.setSpacing(8)

        header = QHBoxLayout()
        recipes_label = QLabel("Recipes")
        recipes_label.setProperty("role", "heading")
        header.addWidget(recipes_label)
        header.addStretch()

        self.show_items_btn = QPushButton("Items")
        self.show_items_btn.setProperty("btn", "secondary")
        self.show_items_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        header.addWidget(self.show_items_btn)

        self.show_saved_btn = QPushButton("Saved Lists")
        self.show_saved_btn.setProperty("btn", "secondary")
        self.show_saved_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        header.addWidget(self.show_saved_btn)
        picker_layout.addLayout(header)

        self.recipe_search = QLineEdit()
        self.recipe_search.setPlaceholderText("Search recipes...")
        self.recipe_search.setClearButtonEnabled(True)
        self.recipe_search.setFixedHeight(30)
        picker_layout.addWidget(self.recipe_search)

        self.tag_scroll = QScrollArea()
        self.tag_scroll.setWidgetResizable(True)
        self.tag_scroll.setFixedHeight(34)
        self.tag_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.tag_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.tag_scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        self.tag_bar_widget = QWidget()
        self.tag_bar_widget.setStyleSheet("background: transparent;")
        self.tag_bar_layout = QHBoxLayout(self.tag_bar_widget)
        self.tag_bar_layout.setContentsMargins(0, 0, 0, 0)
        self.tag_bar_layout.setSpacing(4)
        self.tag_bar_layout.addStretch()
        self.tag_scroll.setWidget(self.tag_bar_widget)
        picker_layout.addWidget(self.tag_scroll)

        self._active_tag = None
        self._recipe_cards = []

        self.recipe_scroll = QScrollArea()
        self.recipe_scroll.setWidgetResizable(True)
        self.recipe_scroll_widget = QWidget()
        self.recipe_scroll_widget.setStyleSheet("background: transparent;")
        self.recipe_scroll_layout = QVBoxLayout(self.recipe_scroll_widget)
        self.recipe_scroll_layout.setContentsMargins(2, 2, 2, 2)
        self.recipe_scroll_layout.setSpacing(6)
        self.recipe_scroll.setWidget(self.recipe_scroll_widget)
        picker_layout.addWidget(self.recipe_scroll, 1)

        self.left_stack.addWidget(self.picker_page)

        # --- page 1: saved lists --- #
        self.saved_page = QWidget()
        saved_layout = QVBoxLayout(self.saved_page)
        saved_layout.setContentsMargins(0, 0, 0, 0)
        saved_layout.setSpacing(8)

        saved_header = QHBoxLayout()
        saved_label = QLabel("Saved Lists")
        saved_label.setProperty("role", "heading")
        saved_header.addWidget(saved_label)
        saved_header.addStretch()

        self.back_to_recipes_btn = QPushButton("Back")
        self.back_to_recipes_btn.setProperty("btn", "secondary")
        self.back_to_recipes_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        saved_header.addWidget(self.back_to_recipes_btn)
        saved_layout.addLayout(saved_header)

        self.saved_scroll = QScrollArea()
        self.saved_scroll.setWidgetResizable(True)
        self.saved_scroll_widget = QWidget()
        self.saved_scroll_widget.setStyleSheet("background: transparent;")
        self.saved_scroll_layout = QVBoxLayout(self.saved_scroll_widget)
        self.saved_scroll_layout.setContentsMargins(2, 2, 2, 2)
        self.saved_scroll_layout.setSpacing(6)
        self.saved_scroll.setWidget(self.saved_scroll_widget)
        saved_layout.addWidget(self.saved_scroll, 1)

        self.left_stack.addWidget(self.saved_page)

        # --- page 2: item picker --- #
        self.item_picker_page = QWidget()
        item_picker_layout = QVBoxLayout(self.item_picker_page)
        item_picker_layout.setContentsMargins(0, 0, 0, 0)
        item_picker_layout.setSpacing(8)

        item_header = QHBoxLayout()
        items_label = QLabel("Items")
        items_label.setProperty("role", "heading")
        item_header.addWidget(items_label)
        item_header.addStretch()

        self.back_to_recipes_btn2 = QPushButton("Back")
        self.back_to_recipes_btn2.setProperty("btn", "secondary")
        self.back_to_recipes_btn2.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        item_header.addWidget(self.back_to_recipes_btn2)
        item_picker_layout.addLayout(item_header)

        self.item_search = QLineEdit()
        self.item_search.setPlaceholderText("Search items...")
        self.item_search.setClearButtonEnabled(True)
        self.item_search.setFixedHeight(30)
        item_picker_layout.addWidget(self.item_search)

        self.item_tag_scroll = QScrollArea()
        self.item_tag_scroll.setWidgetResizable(True)
        self.item_tag_scroll.setFixedHeight(34)
        self.item_tag_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.item_tag_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.item_tag_scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        self.item_tag_bar_widget = QWidget()
        self.item_tag_bar_widget.setStyleSheet("background: transparent;")
        self.item_tag_bar_layout = QHBoxLayout(self.item_tag_bar_widget)
        self.item_tag_bar_layout.setContentsMargins(0, 0, 0, 0)
        self.item_tag_bar_layout.setSpacing(4)
        self.item_tag_bar_layout.addStretch()
        self.item_tag_scroll.setWidget(self.item_tag_bar_widget)
        item_picker_layout.addWidget(self.item_tag_scroll)

        self._active_item_tag = None

        self.item_scroll = QScrollArea()
        self.item_scroll.setWidgetResizable(True)
        self.item_scroll_widget = QWidget()
        self.item_scroll_widget.setStyleSheet("background: transparent;")
        self.item_scroll_layout = QVBoxLayout(self.item_scroll_widget)
        self.item_scroll_layout.setContentsMargins(2, 2, 2, 2)
        self.item_scroll_layout.setSpacing(4)
        self.item_scroll.setWidget(self.item_scroll_widget)
        item_picker_layout.addWidget(self.item_scroll, 1)

        self.left_stack.addWidget(self.item_picker_page)
        self._item_rows = []

        self.layout.addWidget(self.left_panel, 0, 0)
        left_layout.addWidget(self.left_stack)

        self._refresh_recipe_cards()

    # ── recipe picker ──────────────────────────────────────────── #

    def _refresh_recipe_cards(self):
        while self.recipe_scroll_layout.count():
            child = self.recipe_scroll_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        self._recipe_cards = []
        recipes = Recipe().get_recipes()
        recipes.sort(key=lambda x: x[0])

        if not recipes:
            empty = QLabel("No recipes yet — create some first!")
            empty.setProperty("role", "faint")
            self.recipe_scroll_layout.addWidget(empty)
        else:
            for name, _ in recipes:
                card = RecipePickerCard(name, self._add_recipe_to_cart)
                self._recipe_cards.append(card)
                self.recipe_scroll_layout.addWidget(card)

        self.recipe_scroll_layout.addStretch()
        self._refresh_tag_bar()
        self._active_tag = None
        self.recipe_search.clear()

    def _refresh_tag_bar(self):
        while self.tag_bar_layout.count():
            child = self.tag_bar_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        t = theme.theme()
        tags = sorted(Recipe().get_recipe_tags())

        if not tags:
            self.tag_scroll.setVisible(False)
            return

        self.tag_scroll.setVisible(True)

        def chip_css() -> str:
            return f"""
                QPushButton {{
                    background-color: {t.surface};
                    color: {t.text_dim};
                    border: 1px solid {t.border};
                    border-radius: 13px;
                    padding: 0 12px;
                    font-size: 11px;
                    font-weight: 600;
                }}
                QPushButton:hover {{
                    background-color: {t.border};
                    color: {t.text};
                }}
                QPushButton:checked {{
                    background-color: {t.accent};
                    color: {t.accent_fg};
                    border-color: {t.accent};
                }}
            """

        fav_btn = QPushButton("★ Favourites")
        fav_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        fav_btn.setCheckable(True)
        fav_btn.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        fav_btn.setFixedHeight(26)
        fav_btn.setStyleSheet(chip_css())
        fav_btn.clicked.connect(lambda checked: self._on_tag_clicked("★ Favourites", checked))
        self.tag_bar_layout.addWidget(fav_btn)

        for tag in tags:
            btn = QPushButton(tag)
            btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            btn.setCheckable(True)
            btn.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
            btn.setFixedHeight(26)
            btn.setStyleSheet(chip_css())
            btn.clicked.connect(lambda checked, tg=tag: self._on_tag_clicked(tg, checked))
            self.tag_bar_layout.addWidget(btn)

        self.tag_bar_layout.addStretch()

    def _on_tag_clicked(self, tag, checked):
        self._active_tag = tag if checked else None

        for i in range(self.tag_bar_layout.count()):
            w = self.tag_bar_layout.itemAt(i).widget()
            if w and isinstance(w, QPushButton) and w.text() != tag:
                w.setChecked(False)

        self._filter_recipe_cards()

    def _filter_recipe_cards(self, _text=None):
        search = self.recipe_search.text().lower().strip()
        for card in self._recipe_cards:
            name_match = not search or search in card._name.lower()
            if self._active_tag == "★ Favourites":
                doc = Recipe().get_recipe_details(card._name)
                tag_match = doc.get("is_favourite", False) if doc else False
            else:
                tag_match = not self._active_tag or self._active_tag in card.tags
            card.setVisible(name_match and tag_match)

    # ── item picker ────────────────────────────────────────────── #

    def _show_item_picker(self):
        self._refresh_item_rows()
        self.left_stack.setCurrentIndex(2)

    def _refresh_item_rows(self):
        while self.item_scroll_layout.count():
            child = self.item_scroll_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        self._item_rows = []
        t = theme.theme()
        item_obj = Item()
        names = sorted(item_obj.get_item_names())

        for name in names:
            row = QWidget()
            row.setObjectName("item_pick_row")
            row.setFixedHeight(38)
            row.setStyleSheet(theme.inline_card_css("item_pick_row", radius=6))
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(10, 4, 6, 4)
            row_layout.setSpacing(6)

            label = QLabel(name)
            label.setStyleSheet(f"color: {t.text}; font-size: 12px;")
            row_layout.addWidget(label, 1)

            spin = QSpinBox()
            spin.setMinimum(1)
            spin.setMaximum(99)
            spin.setValue(1)
            spin.setFixedWidth(50)
            spin.setFixedHeight(26)
            row_layout.addWidget(spin)

            add_btn = QPushButton("+")
            add_btn.setFixedSize(28, 28)
            add_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            add_btn.setStyleSheet(theme.mini_primary_btn_css(radius=14, font_size=16))
            add_btn.clicked.connect(lambda checked, n=name, s=spin: self._add_extra_item(n, s.value()))
            row_layout.addWidget(add_btn)

            row._item_name = name
            details = item_obj.get_item_details(name)
            row._item_tags = details.get("tags", []) if details else []
            self._item_rows.append(row)
            self.item_scroll_layout.addWidget(row)

        self.item_scroll_layout.addStretch()
        self._refresh_item_tag_bar()

    def _filter_item_rows(self, _text=None):
        search = self.item_search.text().lower().strip()
        for row in self._item_rows:
            name_match = not search or search in row._item_name.lower()
            tag_match = not self._active_item_tag or self._active_item_tag in row._item_tags
            row.setVisible(name_match and tag_match)

    def _refresh_item_tag_bar(self):
        while self.item_tag_bar_layout.count():
            child = self.item_tag_bar_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        t = theme.theme()
        tags = sorted(Item().get_item_tags())

        if not tags:
            self.item_tag_scroll.setVisible(False)
            return

        self.item_tag_scroll.setVisible(True)
        for tag in tags:
            btn = QPushButton(tag)
            btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            btn.setCheckable(True)
            btn.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
            btn.setFixedHeight(26)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {t.surface};
                    color: {t.text_dim};
                    border: 1px solid {t.border};
                    border-radius: 13px;
                    padding: 0 12px;
                    font-size: 11px;
                    font-weight: 600;
                }}
                QPushButton:hover {{
                    background-color: {t.border};
                    color: {t.text};
                }}
                QPushButton:checked {{
                    background-color: {t.accent};
                    color: {t.accent_fg};
                    border-color: {t.accent};
                }}
            """)
            btn.clicked.connect(lambda checked, tg=tag: self._on_item_tag_clicked(tg, checked))
            self.item_tag_bar_layout.addWidget(btn)

        self.item_tag_bar_layout.addStretch()

    def _on_item_tag_clicked(self, tag, checked):
        self._active_item_tag = tag if checked else None

        for i in range(self.item_tag_bar_layout.count()):
            w = self.item_tag_bar_layout.itemAt(i).widget()
            if w and isinstance(w, QPushButton) and w.text() != tag:
                w.setChecked(False)

        self._filter_item_rows()

    # ── saved lists ────────────────────────────────────────────── #

    def _show_saved_lists(self):
        self._refresh_saved_list()
        self.left_stack.setCurrentIndex(1)

    def _show_recipes(self):
        self.left_stack.setCurrentIndex(0)

    def _refresh_saved_list(self):
        while self.saved_scroll_layout.count():
            child = self.saved_scroll_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        saved = ShoppingList().get_all_lists()

        if not saved:
            empty = QLabel("No saved lists yet")
            empty.setProperty("role", "faint")
            self.saved_scroll_layout.addWidget(empty)
        else:
            for name, lid, date in saved:
                card = SavedListCard(name, lid, date, self._load_saved, self._delete_saved)
                self.saved_scroll_layout.addWidget(card)

        self.saved_scroll_layout.addStretch()

    def _load_saved(self, list_id):
        self.current_list_id = list_id
        list_data = ShoppingList().get_list(list_id)
        if not list_data:
            return

        self.recipe_entries = list_data.get("recipe_entries", [])
        self.extra_items = list_data.get("extra_items", [])
        self.name_input.setText(list_data.get("name", ""))

        lt_missing = list_data.get("lt_missing", [])
        self.lt_have = {}
        for name in lt_missing:
            self.lt_have[name] = False

        self._refresh_cart()
        self._show_recipes()

    def _delete_saved(self, list_id):
        ShoppingList().delete_list(list_id)
        self._refresh_saved_list()
