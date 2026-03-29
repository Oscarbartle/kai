from kai.core.recipe_scraper import scrape_recipe
from kai.utils.ingredient_matcher import match_ingredients
from kai.objects.item import Item
from kai.objects.recipe import Recipe
from kai.ui.layouts.items_add import ItemsAdd
from kai.ui import theme

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QSpinBox, QDoubleSpinBox, QComboBox, QTextEdit, QScrollArea,
    QStackedWidget, QStyle, QStyleOption, QDialog, QCheckBox, QSizePolicy,
    QApplication,
)
from PySide6.QtGui import QPainter, QCursor
from PySide6.QtCore import Qt


class IngredientRow(QWidget):
    """Single row for mapping a scraped ingredient to an existing item."""

    def __init__(self, raw_text: str, existing_items: list[str],
                 best_match: str | None = None):
        super().__init__()
        self.raw_text = raw_text
        self._existing_items = existing_items

        t = theme.theme()

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(10)

        # skip checkbox
        self.skip_cb = QCheckBox()
        self.skip_cb.setToolTip("Skip this ingredient")
        self.skip_cb.toggled.connect(self._on_skip_toggled)
        layout.addWidget(self.skip_cb)

        # left: raw text
        left = QVBoxLayout()
        left.setSpacing(2)
        raw_label = QLabel(raw_text)
        raw_label.setWordWrap(True)
        raw_label.setStyleSheet(f"color: {t.text}; font-size: 12px;")
        left.addWidget(raw_label)
        layout.addLayout(left, 2)

        # right: item picker + amount + unit
        right = QVBoxLayout()
        right.setSpacing(4)

        # item combo
        combo_row = QHBoxLayout()
        combo_row.setSpacing(6)
        self.item_combo = QComboBox()
        self.item_combo.addItem("— None —")
        for name in sorted(existing_items):
            self.item_combo.addItem(name)
        if best_match:
            idx = self.item_combo.findText(best_match)
            if idx >= 0:
                self.item_combo.setCurrentIndex(idx)
        self.item_combo.setSizePolicy(QSizePolicy.Policy.Expanding,
                                       QSizePolicy.Policy.Fixed)
        combo_row.addWidget(self.item_combo, 1)

        self.add_item_btn = QPushButton("+ New Item")
        self.add_item_btn.setFixedHeight(28)
        self.add_item_btn.setProperty("btn", "secondary")
        self.add_item_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        combo_row.addWidget(self.add_item_btn)
        right.addLayout(combo_row)

        # amount + unit row
        qty_row = QHBoxLayout()
        qty_row.setSpacing(6)

        self.amount_spin = QSpinBox()
        self.amount_spin.setMinimum(1)
        self.amount_spin.setMaximum(99999)
        self.amount_spin.setValue(1)
        self.amount_spin.setFixedHeight(28)

        self.amount_spin_float = QDoubleSpinBox()
        self.amount_spin_float.setMinimum(0.1)
        self.amount_spin_float.setMaximum(9999)
        self.amount_spin_float.setValue(1.0)
        self.amount_spin_float.setDecimals(1)
        self.amount_spin_float.setSingleStep(0.1)
        self.amount_spin_float.setFixedHeight(28)

        self.amount_stack = QStackedWidget()
        self.amount_stack.addWidget(self.amount_spin)
        self.amount_stack.addWidget(self.amount_spin_float)
        self.amount_stack.setCurrentIndex(0)
        qty_row.addWidget(self.amount_stack, 1)

        self.unit_combo = QComboBox()
        self.unit_combo.addItems(["g", "kg", "mL", "L", "ea"])
        self.unit_combo.setCurrentText("ea")
        self.unit_combo.setFixedHeight(28)
        self.unit_combo.setMinimumWidth(58)
        self.unit_combo.currentTextChanged.connect(self._on_unit_changed)
        qty_row.addWidget(self.unit_combo)

        right.addLayout(qty_row)

        layout.addLayout(right, 3)

        self.setStyleSheet(f"""
            QWidget {{
                background: {t.card};
                border: 1px solid {t.border};
                border-radius: 6px;
            }}
        """)

    def _on_unit_changed(self, unit):
        if unit in ("kg", "L"):
            self.amount_spin_float.setValue(float(self.amount_spin.value()))
            self.amount_stack.setCurrentIndex(1)
        else:
            self.amount_spin.setValue(max(1, int(self.amount_spin_float.value())))
            self.amount_stack.setCurrentIndex(0)

    def _on_skip_toggled(self, checked):
        self.item_combo.setEnabled(not checked)
        self.amount_stack.setEnabled(not checked)
        self.unit_combo.setEnabled(not checked)
        self.add_item_btn.setEnabled(not checked)
        opacity = 0.4 if checked else 1.0
        self.setStyleSheet(self.styleSheet())  # refresh

    def refresh_items(self, existing_items: list[str], auto_select: str | None = None):
        """Refresh the item combo after a new item was added."""
        current = self.item_combo.currentText()
        self.item_combo.clear()
        self.item_combo.addItem("— None —")
        for name in sorted(existing_items):
            self.item_combo.addItem(name)
        if auto_select:
            idx = self.item_combo.findText(auto_select)
            if idx >= 0:
                self.item_combo.setCurrentIndex(idx)
        elif current != "— None —":
            idx = self.item_combo.findText(current)
            if idx >= 0:
                self.item_combo.setCurrentIndex(idx)

    def is_skipped(self) -> bool:
        return self.skip_cb.isChecked()

    def get_data(self) -> dict | None:
        if self.is_skipped():
            return None
        item_name = self.item_combo.currentText()
        if item_name == "— None —":
            return None
        unit = self.unit_combo.currentText()
        if unit in ("kg", "L"):
            amount = self.amount_spin_float.value()
        else:
            amount = self.amount_spin.value()
        return {"item_name": item_name, "amount": amount, "unit": unit}


class RecipeImport(QWidget):
    """Multi-step recipe import wizard."""

    def __init__(self, state):
        super().__init__()
        self.state = state
        self._scraped = None
        self._ingredient_rows: list[IngredientRow] = []

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(24, 20, 24, 20)
        self.layout.setSpacing(12)

        self.stack = QStackedWidget()
        self.layout.addWidget(self.stack, 1)

        # nav buttons
        nav = QHBoxLayout()
        nav.setSpacing(8)
        self.back_btn = QPushButton("Back")
        self.back_btn.setProperty("btn", "secondary")
        self.back_btn.setFixedHeight(38)
        self.back_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.back_btn.clicked.connect(self._go_back)
        nav.addWidget(self.back_btn)

        nav.addStretch()

        self.next_btn = QPushButton("Fetch Recipe")
        self.next_btn.setProperty("btn", "primary")
        self.next_btn.setFixedHeight(38)
        self.next_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.next_btn.clicked.connect(self._go_next)
        nav.addWidget(self.next_btn)

        self.layout.addLayout(nav)

        self._build_step_url()
        self._build_step_details()
        self._build_step_ingredients()

        self.stack.setCurrentIndex(0)
        self._update_nav()

    def paintEvent(self, event):
        opt = QStyleOption()
        opt.initFrom(self)
        p = QPainter(self)
        self.style().drawPrimitive(QStyle.PE_Widget, opt, p, self)

    # ── step 1: URL input ─────────────────────────────────────── #

    def _build_step_url(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        t = theme.theme()

        heading = QLabel("Import Recipe from URL")
        heading.setProperty("role", "heading")
        layout.addWidget(heading)

        hint = QLabel("Paste a recipe URL from a supported website.")
        hint.setProperty("role", "dim")
        layout.addWidget(hint)

        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("https://www.example.com/recipe/...")
        self.url_input.returnPressed.connect(self._go_next)
        layout.addWidget(self.url_input)

        self.url_status = QLabel("")
        self.url_status.setWordWrap(True)
        layout.addWidget(self.url_status)

        layout.addStretch()
        self.stack.addWidget(page)

    # ── step 2: review details ────────────────────────────────── #

    def _build_step_details(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        heading = QLabel("Review Recipe Details")
        heading.setProperty("role", "heading")
        layout.addWidget(heading)

        name_label = QLabel("Name")
        name_label.setProperty("role", "dim")
        layout.addWidget(name_label)
        self.detail_name = QLineEdit()
        layout.addWidget(self.detail_name)

        servings_row = QHBoxLayout()
        servings_col = QVBoxLayout()
        servings_col.setSpacing(4)
        servings_label = QLabel("Servings")
        servings_label.setProperty("role", "dim")
        servings_col.addWidget(servings_label)
        self.detail_servings = QSpinBox()
        self.detail_servings.setMinimum(1)
        self.detail_servings.setFixedWidth(80)
        servings_col.addWidget(self.detail_servings)
        servings_row.addLayout(servings_col)
        servings_row.addStretch()
        layout.addLayout(servings_row)

        tags_label = QLabel("Tags")
        tags_label.setProperty("role", "dim")
        layout.addWidget(tags_label)
        self.detail_tags = QLineEdit()
        self.detail_tags.setPlaceholderText("e.g. Dinner, Italian")
        layout.addWidget(self.detail_tags)

        inst_label = QLabel("Instructions")
        inst_label.setProperty("role", "dim")
        layout.addWidget(inst_label)
        self.detail_instructions = QTextEdit()
        layout.addWidget(self.detail_instructions, 1)

        self.stack.addWidget(page)

    # ── step 3: ingredient matching ───────────────────────────── #

    def _build_step_ingredients(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        heading = QLabel("Match Ingredients")
        heading.setProperty("role", "heading")
        layout.addWidget(heading)

        hint = QLabel(
            "Map each ingredient to an existing item. "
            "Set the amount and unit, or skip ingredients you don't need."
        )
        hint.setProperty("role", "dim")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self.ing_scroll = QScrollArea()
        self.ing_scroll.setWidgetResizable(True)

        self.ing_container = QWidget()
        self.ing_container.setStyleSheet("background: transparent;")
        self.ing_layout = QVBoxLayout(self.ing_container)
        self.ing_layout.setContentsMargins(2, 2, 2, 2)
        self.ing_layout.setSpacing(6)

        self.ing_scroll.setWidget(self.ing_container)
        layout.addWidget(self.ing_scroll, 1)

        # summary label
        self.ing_summary = QLabel("")
        self.ing_summary.setProperty("role", "dim")
        layout.addWidget(self.ing_summary)

        self.stack.addWidget(page)

    # ── navigation ────────────────────────────────────────────── #

    def _update_nav(self):
        idx = self.stack.currentIndex()
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

        # populate step 2
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
        # clear old rows
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
            self._ingredient_rows.append(row)
            self.ing_layout.addWidget(row)

        self.ing_layout.addStretch()
        self._update_ingredient_summary()

    def _update_ingredient_summary(self):
        total = len(self._ingredient_rows)
        mapped = sum(
            1 for r in self._ingredient_rows
            if not r.is_skipped() and r.item_combo.currentText() != "— None —"
        )
        skipped = sum(1 for r in self._ingredient_rows if r.is_skipped())
        self.ing_summary.setText(
            f"{mapped} of {total} ingredients mapped, {skipped} skipped"
        )

    def _open_add_item(self, row: IngredientRow):
        """Open the ItemsAdd dialog to create a new item, then refresh combos."""
        dialog = QDialog(self)
        dialog.setWindowTitle("Add New Item")
        dialog.setMinimumSize(480, 420)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(0, 0, 0, 0)

        items_add = ItemsAdd(self.state)
        layout.addWidget(items_add)

        dialog.exec()

        # refresh all ingredient rows with updated item list
        new_existing = Item().get_item_names()
        # find newly added items
        old_names = set(row._existing_items)
        new_names = set(new_existing) - old_names

        auto_select = new_names.pop() if len(new_names) == 1 else None

        for r in self._ingredient_rows:
            r.refresh_items(new_existing,
                            auto_select=auto_select if r is row else None)
            r._existing_items = new_existing

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

        # close parent dialog
        parent = self.parent()
        while parent:
            if hasattr(parent, "accept"):
                parent.accept()
                break
            parent = parent.parent()
