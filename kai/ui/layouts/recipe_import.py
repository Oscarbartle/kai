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
    QApplication, QFrame,
)
from PySide6.QtGui import QPainter, QCursor, QColor
from PySide6.QtCore import Qt, QSortFilterProxyModel, QStringListModel
from PySide6.QtWidgets import QCompleter


class IngredientRow(QWidget):
    """Single row for mapping a scraped ingredient to an existing item."""

    def __init__(self, raw_text: str, existing_items: list[str],
                 best_match: str | None = None):
        super().__init__()
        self.raw_text = raw_text
        self._existing_items = list(existing_items)
        self._omitted = False

        t = theme.theme()

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 10)
        root.setSpacing(8)

        # ── top row: raw text + omit button ──────────────────── #
        top = QHBoxLayout()
        top.setSpacing(8)
        top.setContentsMargins(0, 0, 0, 0)

        self._raw_label = QLabel(raw_text)
        self._raw_label.setWordWrap(True)
        self._raw_label.setStyleSheet(f"color: {t.text}; font-size: 12px; font-weight: 600;")
        top.addWidget(self._raw_label, 1)

        self._omit_btn = QPushButton("Omit")
        self._omit_btn.setFixedHeight(26)
        self._omit_btn.setFixedWidth(56)
        self._omit_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._omit_btn.setCheckable(True)
        self._omit_btn.setToolTip("Exclude this ingredient from the recipe")
        self._omit_btn.toggled.connect(self._on_omit_toggled)
        top.addWidget(self._omit_btn)

        root.addLayout(top)

        # ── bottom row: item search + amount + unit + nominal ── #
        self._controls = QWidget()
        controls_layout = QHBoxLayout(self._controls)
        controls_layout.setContentsMargins(0, 0, 0, 0)
        controls_layout.setSpacing(8)

        # searchable item combo
        self.item_combo = QComboBox()
        self.item_combo.setEditable(True)
        self.item_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.item_combo.lineEdit().setPlaceholderText("Search items…")
        self.item_combo.addItem("— None —")
        for name in sorted(existing_items):
            self.item_combo.addItem(name)

        completer = QCompleter(sorted(existing_items), self)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self.item_combo.setCompleter(completer)
        self._completer = completer

        if best_match:
            idx = self.item_combo.findText(best_match)
            if idx >= 0:
                self.item_combo.setCurrentIndex(idx)
        self.item_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.item_combo.setFixedHeight(30)
        controls_layout.addWidget(self.item_combo, 3)

        # amount spinbox (int / float stacked)
        self.amount_spin = QSpinBox()
        self.amount_spin.setMinimum(1)
        self.amount_spin.setMaximum(99999)
        self.amount_spin.setValue(1)
        self.amount_spin.setFixedHeight(30)
        self.amount_spin.setFixedWidth(64)

        self.amount_spin_float = QDoubleSpinBox()
        self.amount_spin_float.setMinimum(0.1)
        self.amount_spin_float.setMaximum(9999)
        self.amount_spin_float.setValue(1.0)
        self.amount_spin_float.setDecimals(1)
        self.amount_spin_float.setSingleStep(0.1)
        self.amount_spin_float.setFixedHeight(30)
        self.amount_spin_float.setFixedWidth(64)

        self.amount_stack = QStackedWidget()
        self.amount_stack.addWidget(self.amount_spin)
        self.amount_stack.addWidget(self.amount_spin_float)
        self.amount_stack.setCurrentIndex(0)
        self.amount_stack.setFixedWidth(64)
        controls_layout.addWidget(self.amount_stack)

        self.unit_combo = QComboBox()
        self.unit_combo.addItems(["g", "kg", "mL", "L", "ea"])
        self.unit_combo.setCurrentText("ea")
        self.unit_combo.setFixedHeight(30)
        self.unit_combo.setFixedWidth(62)
        self.unit_combo.currentTextChanged.connect(self._on_unit_changed)
        controls_layout.addWidget(self.unit_combo)

        # nominal checkbox
        self.nominal_cb = QCheckBox("Nominal")
        self.nominal_cb.setToolTip(
            "Use when an exact amount doesn't matter (e.g. olive oil, salt).\n"
            "Counted as 1 unit on shopping lists and excluded from cost totals."
        )
        self.nominal_cb.setFixedHeight(30)
        self.nominal_cb.setStyleSheet(theme.checkbox_css())
        self.nominal_cb.toggled.connect(self._on_nominal_toggled)
        controls_layout.addWidget(self.nominal_cb)

        # new item button
        self.add_item_btn = QPushButton("+ New")
        self.add_item_btn.setFixedHeight(30)
        self.add_item_btn.setFixedWidth(58)
        self.add_item_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        controls_layout.addWidget(self.add_item_btn)

        root.addWidget(self._controls)

        self._apply_style()

    # ── style ─────────────────────────────────────────────────── #

    def _apply_style(self):
        t = theme.theme()
        if self._omitted:
            self.setStyleSheet(f"""
                QWidget {{
                    background: transparent;
                    border: 1px solid {t.border};
                    border-radius: 8px;
                    opacity: 0.5;
                }}
            """)
            self._omit_btn.setStyleSheet(f"""
                QPushButton {{
                    background: {t.danger};
                    color: white;
                    border: none;
                    border-radius: 5px;
                    font-size: 11px;
                    font-weight: bold;
                }}
            """)
            self._raw_label.setStyleSheet(
                f"color: {t.text_faint}; font-size: 12px; font-weight: 600;"
                "text-decoration: line-through;"
            )
        else:
            self.setStyleSheet(f"""
                QWidget {{
                    background: {t.card};
                    border: 1px solid {t.border};
                    border-radius: 8px;
                }}
            """)
            self._omit_btn.setStyleSheet(f"""
                QPushButton {{
                    background: {t.surface};
                    color: {t.text_dim};
                    border: 1px solid {t.border};
                    border-radius: 5px;
                    font-size: 11px;
                    font-weight: 600;
                }}
                QPushButton:hover {{
                    background: {t.danger};
                    color: white;
                    border-color: {t.danger};
                }}
            """)
            self._raw_label.setStyleSheet(
                f"color: {t.text}; font-size: 12px; font-weight: 600;"
            )

    def _on_omit_toggled(self, checked):
        self._omitted = checked
        self._omit_btn.setText("Omitted" if checked else "Omit")
        self._controls.setEnabled(not checked)
        self._apply_style()

    def _on_unit_changed(self, unit):
        if unit in ("kg", "L"):
            self.amount_spin_float.setValue(float(self.amount_spin.value()))
            self.amount_stack.setCurrentIndex(1)
        else:
            self.amount_spin.setValue(max(1, int(self.amount_spin_float.value())))
            self.amount_stack.setCurrentIndex(0)

    def _on_nominal_toggled(self, checked):
        self.amount_stack.setEnabled(not checked)
        self.unit_combo.setEnabled(not checked)

    # ── public API ────────────────────────────────────────────── #

    def refresh_items(self, existing_items: list[str], auto_select: str | None = None):
        """Refresh the item combo + completer after a new item was added."""
        current = self.item_combo.currentText()
        self.item_combo.clear()
        self.item_combo.addItem("— None —")
        for name in sorted(existing_items):
            self.item_combo.addItem(name)

        self._completer.setModel(QStringListModel(sorted(existing_items), self._completer))
        self._existing_items = list(existing_items)

        if auto_select:
            idx = self.item_combo.findText(auto_select)
            if idx >= 0:
                self.item_combo.setCurrentIndex(idx)
        elif current not in ("— None —", ""):
            idx = self.item_combo.findText(current)
            if idx >= 0:
                self.item_combo.setCurrentIndex(idx)

    def is_omitted(self) -> bool:
        return self._omitted

    def get_data(self) -> dict | None:
        if self._omitted:
            return None
        item_name = self.item_combo.currentText().strip()
        if not item_name or item_name == "— None —":
            return None
        nominal = self.nominal_cb.isChecked()
        unit = self.unit_combo.currentText()
        if nominal:
            return {"item_name": item_name, "amount": 1, "unit": "ea", "nominal": True}
        if unit in ("kg", "L"):
            amount = self.amount_spin_float.value()
        else:
            amount = self.amount_spin.value()
        return {"item_name": item_name, "amount": amount, "unit": unit, "nominal": False}


# ── step progress indicator ───────────────────────────────────── #

class _StepDots(QWidget):
    def __init__(self, count: int, parent=None):
        super().__init__(parent)
        self._count = count
        self._current = 0
        self.setFixedHeight(12)

    def set_step(self, idx: int):
        self._current = idx
        self.update()

    def paintEvent(self, event):
        t = theme.theme()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        dot_r = 4
        gap = 16
        total_w = self._count * (dot_r * 2) + (self._count - 1) * gap
        x = (self.width() - total_w) // 2
        cy = self.height() // 2
        for i in range(self._count):
            cx = x + i * (dot_r * 2 + gap) + dot_r
            if i == self._current:
                p.setBrush(QColor(t.accent))
                p.setPen(Qt.PenStyle.NoPen)
                p.drawEllipse(cx - dot_r, cy - dot_r, dot_r * 2, dot_r * 2)
            else:
                p.setBrush(QColor(t.border))
                p.setPen(Qt.PenStyle.NoPen)
                p.drawEllipse(cx - dot_r + 1, cy - dot_r + 1, (dot_r - 1) * 2, (dot_r - 1) * 2)


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
        self._dots = _StepDots(3)
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
        layout.setSpacing(12)

        heading = QLabel("Import Recipe from URL")
        heading.setProperty("role", "heading")
        layout.addWidget(heading)

        hint = QLabel("Paste a recipe URL from a supported website.")
        hint.setProperty("role", "dim")
        layout.addWidget(hint)

        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("https://www.example.com/recipe/…")
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
        layout.setSpacing(10)

        heading = QLabel("Review Recipe Details")
        heading.setProperty("role", "heading")
        layout.addWidget(heading)

        t = theme.theme()

        name_label = QLabel("Name")
        name_label.setProperty("role", "dim")
        layout.addWidget(name_label)
        self.detail_name = QLineEdit()
        layout.addWidget(self.detail_name)

        row2 = QHBoxLayout()
        row2.setSpacing(16)

        servings_col = QVBoxLayout()
        servings_col.setSpacing(4)
        servings_label = QLabel("Servings")
        servings_label.setProperty("role", "dim")
        servings_col.addWidget(servings_label)
        self.detail_servings = QSpinBox()
        self.detail_servings.setMinimum(1)
        self.detail_servings.setFixedWidth(80)
        servings_col.addWidget(self.detail_servings)
        row2.addLayout(servings_col)

        tags_col = QVBoxLayout()
        tags_col.setSpacing(4)
        tags_label = QLabel("Tags")
        tags_label.setProperty("role", "dim")
        tags_col.addWidget(tags_label)
        self.detail_tags = QLineEdit()
        self.detail_tags.setPlaceholderText("e.g. Dinner, Italian")
        tags_col.addWidget(self.detail_tags)
        row2.addLayout(tags_col, 1)

        layout.addLayout(row2)

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
        layout.setSpacing(8)

        header_row = QHBoxLayout()
        heading = QLabel("Match Ingredients")
        heading.setProperty("role", "heading")
        header_row.addWidget(heading, 1)

        self.ing_summary = QLabel("")
        self.ing_summary.setProperty("role", "dim")
        self.ing_summary.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        header_row.addWidget(self.ing_summary)
        layout.addLayout(header_row)

        hint = QLabel(
            "Map each scraped ingredient to an item in your pantry. "
            "Search by typing in the item box. Mark as Nominal if an exact amount doesn't matter, "
            "or Omit to exclude it from the recipe."
        )
        hint.setProperty("role", "dim")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        # filter bar
        self._ing_search = QLineEdit()
        self._ing_search.setPlaceholderText("Filter ingredients…")
        self._ing_search.setFixedHeight(32)
        self._ing_search.textChanged.connect(self._filter_rows)
        layout.addWidget(self._ing_search)

        self.ing_scroll = QScrollArea()
        self.ing_scroll.setWidgetResizable(True)
        self.ing_scroll.setStyleSheet(theme.scrollbar_css())

        self.ing_container = QWidget()
        self.ing_container.setStyleSheet("background: transparent;")
        self.ing_layout = QVBoxLayout(self.ing_container)
        self.ing_layout.setContentsMargins(2, 2, 2, 2)
        self.ing_layout.setSpacing(6)

        self.ing_scroll.setWidget(self.ing_container)
        layout.addWidget(self.ing_scroll, 1)

        self.stack.addWidget(page)

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
