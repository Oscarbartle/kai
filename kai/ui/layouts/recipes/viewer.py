from __future__ import annotations

from kai.objects.recipe import Recipe
from kai.ui.widgets.recipe_details import RecipeDetails, invalidate_recipe_card_cache
from kai.ui.widgets.recipe_view import RecipeView
from kai.ui import theme

from PySide6.QtWidgets import (
    QLabel, QWidget, QVBoxLayout, QHBoxLayout, QStyle, QStyleOption,
    QScrollArea, QStackedWidget, QPushButton, QComboBox, QLineEdit,
)
from PySide6.QtGui import QPainter, QCursor
from PySide6.QtCore import Qt


# Sort keys read attributes already on the RecipeDetails card — cost is cached
# in RecipeDetails._calculate_cost so cost-based sorts no longer recompute.
# (label, card_key_fn, reverse)
_SORTS: list[tuple[str, callable, bool]] = [
    ("A–Z",              lambda c: c.name.lower(),                                 False),
    ("Z–A",              lambda c: c.name.lower(),                                 True),
    ("Cheapest",         lambda c: c.estimated_cost if c.estimated_cost else 9999, False),
    ("Most Expensive",   lambda c: c.estimated_cost or 0,                          True),
    ("Favourites First", lambda c: c.is_favourite,                                 True),
]
_SORT_LABELS = [s[0] for s in _SORTS]


class RecipesViewer(QWidget):
    def __init__(self, state):
        super().__init__()

        self.state = state
        self.active_tag = "All"
        self.active_sort = 0

        self.layout = QVBoxLayout()
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)
        self.setLayout(self.layout)

        self.stack = QStackedWidget()
        self.layout.addWidget(self.stack)

        # page 0: recipe list
        self.list_page = QWidget()
        list_layout = QVBoxLayout(self.list_page)
        list_layout.setContentsMargins(12, 12, 12, 12)
        list_layout.setSpacing(8)

        self.recipes_label = QLabel("Recipes")
        self.recipes_label.setProperty("role", "heading")

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(8)
        header.addWidget(self.recipes_label)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search recipes…")
        self.search_input.setFixedHeight(34)
        self.search_input.setClearButtonEnabled(True)
        self.search_input.textChanged.connect(self._filter_recipes)
        header.addWidget(self.search_input, 1)

        self.sort_combo = QComboBox()
        self.sort_combo.addItems(_SORT_LABELS)
        self.sort_combo.setFixedHeight(34)
        self.sort_combo.setToolTip("Sort recipes")
        self.sort_combo.currentIndexChanged.connect(self._on_sort_changed)
        header.addWidget(self.sort_combo)

        self.import_button = QPushButton("Import URL")
        self.import_button.setFixedHeight(34)
        self.import_button.setProperty("btn", "secondary")
        self.import_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.import_button.setToolTip("Import recipe from website")
        header.addWidget(self.import_button)

        self.add_button = QPushButton("+ Add Recipe")
        self.add_button.setFixedHeight(34)
        self.add_button.setProperty("btn", "primary")
        self.add_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.add_button.setToolTip("Add new recipe")
        header.addWidget(self.add_button)

        list_layout.addLayout(header)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)

        self.scroll_widget = QWidget()
        self.scroll_widget.setStyleSheet("background: transparent;")
        self.scroll_layout = QVBoxLayout(self.scroll_widget)
        self.scroll_layout.setContentsMargins(2, 2, 2, 2)
        self.scroll_layout.setSpacing(5)

        self.scroll_area.setWidget(self.scroll_widget)
        list_layout.addWidget(self.scroll_area)

        self.stack.addWidget(self.list_page)

        # page 1: placeholder for recipe view (swapped dynamically)
        self._view_widget = None

        self.reload_recipes()
        self.connections()

    def paintEvent(self, event):
        opt = QStyleOption()
        opt.initFrom(self)
        p = QPainter(self)
        self.style().drawPrimitive(QStyle.PE_Widget, opt, p, self)

    def connections(self):
        self.state.new_recipes.connect(invalidate_recipe_card_cache)
        self.state.new_items.connect(invalidate_recipe_card_cache)
        self.state.new_recipes.connect(self.reload_recipes)
        self.state.new_items.connect(self.reload_recipes)
        self.state.tag_selected.connect(self.on_tag_selected)

    def on_tag_selected(self, tag: str):
        self.active_tag = tag
        self.reload_recipes()

    def _filter_recipes(self, text: str = ""):
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
        # reorder existing widgets — no card rebuild
        cards = []
        while self.scroll_layout.count():
            item = self.scroll_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                cards.append(w)
        self._sort_and_layout_cards(cards)
        if hasattr(self, "search_input"):
            self._filter_recipes(self.search_input.text())

    def _sort_and_layout_cards(self, cards):
        _, key_fn, reverse = _SORTS[self.active_sort]
        cards.sort(key=key_fn, reverse=reverse)
        for c in cards:
            self.scroll_layout.addWidget(c)
        self.scroll_layout.addStretch()

    def reload_recipes(self):
        while self.scroll_layout.count():
            child = self.scroll_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        recipe_obj = Recipe()
        cards = []
        # iterate the dict once — avoids N redundant _get_id_by_name scans
        for _, doc in recipe_obj.io.all().items():
            name = doc.get("name")
            if not name:
                continue
            if self.active_tag == "★ Favourites":
                if not doc.get("is_favourite", False):
                    continue
            elif self.active_tag != "All":
                if self.active_tag not in (doc.get("tags") or []):
                    continue
            card = RecipeDetails(name, self.state, doc=doc)
            card.recipe_clicked.connect(self._open_recipe)
            cards.append(card)

        self._sort_and_layout_cards(cards)
        if hasattr(self, "search_input"):
            self._filter_recipes(self.search_input.text())

        if self.stack.currentIndex() == 1:
            self._close_recipe()

    def _open_recipe(self, recipe_name):
        if self._view_widget:
            self.stack.removeWidget(self._view_widget)
            self._view_widget.deleteLater()

        view = RecipeView(recipe_name)
        view.back_requested.connect(self._close_recipe)
        self._view_widget = view
        self.stack.addWidget(view)
        self.stack.setCurrentWidget(view)

    def _close_recipe(self):
        if self._view_widget:
            self.stack.removeWidget(self._view_widget)
            self._view_widget.deleteLater()
            self._view_widget = None
        self.stack.setCurrentIndex(0)
