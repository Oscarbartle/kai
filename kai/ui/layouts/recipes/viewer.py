from kai.objects.recipe import Recipe
from kai.ui.widgets.recipe_details import RecipeDetails, invalidate_recipe_card_cache
from kai.ui.widgets.recipe_view import RecipeView
from kai.ui import theme

from PySide6.QtWidgets import QLabel, QWidget, QVBoxLayout, QHBoxLayout, QStyle, QStyleOption, QScrollArea, QStackedWidget, QPushButton
from PySide6.QtGui import QPainter, QCursor
from PySide6.QtCore import Qt


class RecipesViewer(QWidget):
    def __init__(self, state):
        super().__init__()

        self.state = state
        self.active_tag = "All"

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
        header.addWidget(self.recipes_label)
        header.addStretch()

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

    def reload_recipes(self):
        while self.scroll_layout.count():
            child = self.scroll_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        recipes_data = Recipe().get_recipes()
        recipes_data.sort(key=lambda x: x[0])

        for name, recipe_id in recipes_data:
            if self.active_tag == "★ Favourites":
                details = Recipe().get_recipe_details(name)
                if not details or not details.get("is_favourite", False):
                    continue
            elif self.active_tag != "All":
                details = Recipe().get_recipe_details(name)
                if details and self.active_tag not in details.get("tags", []):
                    continue
            card = RecipeDetails(name, self.state)
            card.recipe_clicked.connect(self._open_recipe)
            self.scroll_layout.addWidget(card)

        self.scroll_layout.addStretch()

        # if we were viewing a recipe that got deleted, go back to list
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
