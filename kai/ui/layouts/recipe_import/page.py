from kai.core.recipe_scraper import scrape_recipe
from kai.utils.ingredient_matcher import match_ingredients
from kai.objects.item import Item
from kai.objects.recipe import Recipe
from kai.ui.layouts.items.add import ItemsAdd
from kai.ui.layouts.recipe_import.steps import attach_steps_to_stack
from kai.ui import theme
from kai.ui.widgets.ingredient_row import IngredientRow
from kai.ui.widgets.step_indicator import StepDots

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QStackedWidget, QStyle, QStyleOption, QDialog,
    QApplication, QFrame,
)
from PySide6.QtGui import QPainter, QCursor
from PySide6.QtCore import Qt


class RecipeImport(QWidget):
    """Multi-step recipe import wizard."""

    def __init__(self, state):
        super().__init__()
        self.state = state
        self._scraped = None
        self._ingredient_rows: list[IngredientRow] = []

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 16, 24, 20)
        root.setSpacing(0)

        # step dots
        self._dots = StepDots(3)
        root.addWidget(self._dots)
        root.addSpacing(12)

        self.stack = QStackedWidget()
        root.addWidget(self.stack, 1)
        root.addSpacing(12)

        # separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {theme.theme().border};")
        root.addWidget(sep)
        root.addSpacing(10)

        # nav buttons
        nav = QHBoxLayout()
        nav.setSpacing(8)
        self.back_btn = QPushButton("Back")
        self.back_btn.setProperty("btn", "secondary")
        self.back_btn.setFixedHeight(36)
        self.back_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.back_btn.clicked.connect(self._go_back)
        nav.addWidget(self.back_btn)

        nav.addStretch()

        self.next_btn = QPushButton("Fetch Recipe")
        self.next_btn.setProperty("btn", "primary")
        self.next_btn.setFixedHeight(36)
        self.next_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.next_btn.clicked.connect(self._go_next)
        nav.addWidget(self.next_btn)

        root.addLayout(nav)

        self._url_step, self._details_step, self._ingredients_step = attach_steps_to_stack(
            self.stack, self._go_next, self._filter_rows
        )
        self.url_input = self._url_step.url_input
        self.url_status = self._url_step.url_status
        self.detail_name = self._details_step.detail_name
        self.detail_servings = self._details_step.detail_servings
        self.detail_tags = self._details_step.detail_tags
        self.detail_instructions = self._details_step.detail_instructions
        self.ing_summary = self._ingredients_step.ing_summary
        self._ing_search = self._ingredients_step.ing_search
        self.ing_scroll = self._ingredients_step.ing_scroll
        self.ing_container = self._ingredients_step.ing_container
        self.ing_layout = self._ingredients_step.ing_layout

        self.stack.setCurrentIndex(0)
        self._update_nav()

    def paintEvent(self, event):
        opt = QStyleOption()
        opt.initFrom(self)
        p = QPainter(self)
        self.style().drawPrimitive(QStyle.PE_Widget, opt, p, self)

    # ── navigation ────────────────────────────────────────────── #

    def _update_nav(self):
        idx = self.stack.currentIndex()
        self._dots.set_step(idx)
        self.back_btn.setVisible(idx > 0)
        labels = ["Fetch Recipe", "Next: Ingredients", "Import Recipe"]
        self.next_btn.setText(labels[min(idx, len(labels) - 1)])

    def _go_back(self):
        idx = self.stack.currentIndex()
        if idx > 0:
            self.stack.setCurrentIndex(idx - 1)
            self._update_nav()

    def _go_next(self):
        idx = self.stack.currentIndex()
        if idx == 0:
            self._fetch_recipe()
        elif idx == 1:
            self._populate_ingredients()
            self.stack.setCurrentIndex(2)
            self._update_nav()
        elif idx == 2:
            self._do_import()

    def _fetch_recipe(self):
        url = self.url_input.text().strip()
        if not url:
            self.url_status.setStyleSheet(theme.label_css("danger"))
            self.url_status.setText("Please enter a URL")
            return

        self.url_status.setStyleSheet(theme.label_css("dim"))
        self.url_status.setText("Fetching recipe…")
        QApplication.processEvents()

        try:
            self._scraped = scrape_recipe(url)
        except ValueError as e:
            self.url_status.setStyleSheet(theme.label_css("danger"))
            self.url_status.setText(str(e))
            return

        self.detail_name.setText(self._scraped["title"])
        self.detail_servings.setValue(self._scraped["servings"])
        self.detail_instructions.setPlainText(self._scraped["instructions"])

        self.url_status.setStyleSheet(theme.label_css("success"))
        self.url_status.setText(
            f"Found: {self._scraped['title']} — "
            f"{len(self._scraped['ingredients'])} ingredients"
        )

        self.stack.setCurrentIndex(1)
        self._update_nav()

    def _populate_ingredients(self):
        while self.ing_layout.count():
            child = self.ing_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        self._ingredient_rows.clear()

        if not self._scraped:
            return

        existing = Item().get_item_names()
        matches = match_ingredients(self._scraped["ingredients"], existing)

        for m in matches:
            row = IngredientRow(m["raw_text"], existing, m["best_match"])
            row.add_item_btn.clicked.connect(
                lambda checked, r=row: self._open_add_item(r)
            )
            row._omit_btn.toggled.connect(self._update_ingredient_summary)
            row.item_combo.currentTextChanged.connect(self._update_ingredient_summary)
            self._ingredient_rows.append(row)
            self.ing_layout.addWidget(row)

        self.ing_layout.addStretch()
        self._ing_search.clear()
        self._update_ingredient_summary()

    def _filter_rows(self, text: str):
        q = text.lower().strip()
        for row in self._ingredient_rows:
            row.setVisible(not q or q in row.raw_text.lower())

    def _update_ingredient_summary(self):
        total = len(self._ingredient_rows)
        mapped = sum(
            1 for r in self._ingredient_rows
            if not r.is_omitted() and r.item_combo.currentText().strip() not in ("— None —", "")
        )
        omitted = sum(1 for r in self._ingredient_rows if r.is_omitted())
        parts = [f"{mapped}/{total} mapped"]
        if omitted:
            parts.append(f"{omitted} omitted")
        self.ing_summary.setText("  ·  ".join(parts))

    def _open_add_item(self, row: IngredientRow):
        """Open the ItemsAdd dialog; auto-select the newly created item."""
        old_names = set(row._existing_items)

        dialog = QDialog(self)
        dialog.setWindowTitle("Add New Item")
        dialog.setMinimumSize(480, 420)
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(0, 0, 0, 0)
        items_add = ItemsAdd(self.state)
        layout.addWidget(items_add)
        dialog.exec()

        new_existing = Item().get_item_names()
        new_names = set(new_existing) - old_names
        auto_select = new_names.pop() if len(new_names) == 1 else None

        for r in self._ingredient_rows:
            r.refresh_items(new_existing, auto_select=auto_select if r is row else None)

        self._update_ingredient_summary()

    def _do_import(self):
        name = self.detail_name.text().strip()
        if not name:
            return

        servings = self.detail_servings.value()
        tags = [t.strip() for t in self.detail_tags.text().split(",") if t.strip()]
        instructions = self.detail_instructions.toPlainText().strip()

        ingredients = []
        for row in self._ingredient_rows:
            data = row.get_data()
            if data:
                ingredients.append(data)

        Recipe().create(name, servings, tags, ingredients, instructions)
        self.state.recipes_updated()

        parent = self.parent()
        while parent:
            if hasattr(parent, "accept"):
                parent.accept()
                break
            parent = parent.parent()
