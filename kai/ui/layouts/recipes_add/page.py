from kai.objects.item import Item
from kai.objects.recipe import Recipe
from kai.ui import theme
from kai.ui.layouts.recipes_add.panels import RecipeDetailsPanel, RecipeIngredientsPanel

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton, QHBoxLayout, QStyle, QStyleOption,
    QListWidgetItem
)
from PySide6.QtGui import QPainter, QCursor
from PySide6.QtCore import Qt


class RecipesAdd(QWidget):
    def __init__(self, state, edit_recipe=None):
        super().__init__()

        self.state = state
        self.ingredients_list = []
        self._edit_name = edit_recipe  # recipe name to edit, or None for new

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(20, 18, 20, 18)
        self.layout.setSpacing(14)

        self.create_widgets()
        self.add_layouts()
        self.connections()

        if self._edit_name:
            self._populate_edit_data()

    def paintEvent(self, event):
        opt = QStyleOption()
        opt.initFrom(self)
        p = QPainter(self)
        self.style().drawPrimitive(QStyle.PE_Widget, opt, p, self)

    def create_widgets(self):
        self.left_panel = RecipeDetailsPanel()
        self.right_panel = RecipeIngredientsPanel(on_drop_callback=self._on_items_dropped)

        self.recipe_name = self.left_panel.recipe_name
        self.recipe_servings = self.left_panel.recipe_servings
        self.recipe_tags = self.left_panel.recipe_tags
        self.recipe_instructions = self.left_panel.recipe_instructions

        self.available_search = self.right_panel.available_search
        self.available_list = self.right_panel.available_list
        self.selected_list = self.right_panel.selected_list
        self.add_ing_button = self.right_panel.add_ing_button
        self.remove_ing_button = self.right_panel.remove_ing_button
        self.amount_spin = self.right_panel.amount_spin
        self.amount_spin_float = self.right_panel.amount_spin_float
        self.amount_stack = self.right_panel.amount_stack
        self.unit_combo = self.right_panel.unit_combo
        self.nominal_cb = self.right_panel.nominal_cb
        self.set_qty_button = self.right_panel.set_qty_button

        self._refresh_item_list()

        # ── save button ─────────────────────────────────────── #
        label = "Save Changes" if self._edit_name else "Add Recipe"
        self.button = QPushButton(label)
        self.button.setProperty("btn", "primary")
        self.button.setFixedHeight(40)
        self.button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

    def _populate_edit_data(self):
        doc = Recipe().get_recipe_details(self._edit_name)
        if not doc:
            return
        self.recipe_name.setText(doc.get("name", ""))
        self.recipe_servings.setValue(doc.get("servings", 1))
        self.recipe_tags.setText(", ".join(doc.get("tags", [])))
        self.recipe_instructions.setPlainText(doc.get("instructions", ""))
        for ing in doc.get("ingredients", []):
            name = ing.get("item_name", "")
            amount = ing.get("amount", 1)
            unit = ing.get("unit", "ea")
            nominal = ing.get("nominal", False)
            self.ingredients_list.append({"item_name": name, "amount": amount, "unit": unit, "nominal": nominal})
            self._add_selected_display(name, amount, unit, nominal=nominal)

    def _refresh_item_list(self):
        names = sorted(Item().get_item_names())
        self.right_panel.set_available_items(names)

    def add_layouts(self):
        for w in (self.recipe_name, self.recipe_tags, self.available_search,
                  self.recipe_servings, self.unit_combo,
                  self.amount_spin, self.amount_spin_float):
            w.setStyleSheet(theme.input_css())
        self.recipe_instructions.setStyleSheet(theme.input_css())
        self.available_list.setStyleSheet(theme.list_widget_css())
        self.selected_list.setStyleSheet(theme.list_widget_css())
        self.nominal_cb.setStyleSheet(theme.checkbox_css())
        self.button.setStyleSheet(theme.button_css(primary=True))

        # two-column body
        body = QHBoxLayout()
        body.setSpacing(12)
        body.addWidget(self.left_panel, 5)
        body.addWidget(self.right_panel, 6)

        self.layout.addLayout(body, 1)
        self.layout.addWidget(self.button)

    def connections(self):
        self.button.clicked.connect(self.on_add_recipe)
        self.add_ing_button.clicked.connect(self.on_add_ingredients)
        self.remove_ing_button.clicked.connect(self.on_remove_ingredients)
        self.set_qty_button.clicked.connect(self.on_set_qty)
        self.unit_combo.currentTextChanged.connect(self._on_unit_changed)
        self.available_search.textChanged.connect(self._filter_available)
        self.available_list.itemDoubleClicked.connect(self._on_available_double_click)
        self.selected_list.itemDoubleClicked.connect(self._on_selected_double_click)
        self.selected_list.currentItemChanged.connect(self._on_selected_changed)
        self.state.new_items.connect(self._refresh_item_list)

    def _on_unit_changed(self, unit):
        """Switch between int and float spinner based on unit."""
        if unit in ("kg", "L"):
            # transfer int value to float spinner
            self.amount_spin_float.setValue(float(self.amount_spin.value()))
            self.amount_stack.setCurrentIndex(1)
        else:
            # transfer float value to int spinner
            self.amount_spin.setValue(max(1, int(self.amount_spin_float.value())))
            self.amount_stack.setCurrentIndex(0)

    def _get_current_amount(self):
        if self.unit_combo.currentText() in ("kg", "L"):
            return self.amount_spin_float.value()
        return self.amount_spin.value()

    def _set_current_amount(self, value):
        if self.unit_combo.currentText() in ("kg", "L"):
            self.amount_spin_float.setValue(float(value))
            self.amount_stack.setCurrentIndex(1)
        else:
            self.amount_spin.setValue(max(1, int(value)))
            self.amount_stack.setCurrentIndex(0)

    def _filter_available(self, text):
        search = text.lower()
        for i in range(self.available_list.count()):
            item = self.available_list.item(i)
            item.setHidden(search not in item.text().lower())

    def _on_items_dropped(self, names):
        for name in names:
            name = name.strip()
            if name and not self._ingredient_exists(name):
                self.ingredients_list.append({"item_name": name, "amount": 1, "unit": "ea", "nominal": False})
                self._add_selected_display(name, 1, "ea", nominal=False)

    def on_add_ingredients(self):
        selected = self.available_list.selectedItems()
        for item in selected:
            name = item.text()
            if not self._ingredient_exists(name):
                self.ingredients_list.append({"item_name": name, "amount": 1, "unit": "ea", "nominal": False})
                self._add_selected_display(name, 1, "ea", nominal=False)

    def on_remove_ingredients(self):
        selected = self.selected_list.selectedItems()
        for item in selected:
            name = item.data(Qt.ItemDataRole.UserRole)
            self.ingredients_list = [i for i in self.ingredients_list if i["item_name"] != name]
            self.selected_list.takeItem(self.selected_list.row(item))

    def _on_available_double_click(self, item):
        name = item.text()
        if not self._ingredient_exists(name):
            self.ingredients_list.append({"item_name": name, "amount": 1, "unit": "ea", "nominal": False})
            self._add_selected_display(name, 1, "ea", nominal=False)

    def _on_selected_double_click(self, item):
        name = item.data(Qt.ItemDataRole.UserRole)
        self.ingredients_list = [i for i in self.ingredients_list if i["item_name"] != name]
        self.selected_list.takeItem(self.selected_list.row(item))

    def _ingredient_exists(self, name):
        return any(i["item_name"] == name for i in self.ingredients_list)

    def _add_selected_display(self, name, amount, unit, nominal=False):
        if nominal:
            display = f"~ {name}"
        elif unit == "ea" and amount == 1:
            display = name
        else:
            amt = int(amount) if amount == int(amount) else amount
            display = f"{name}  —  {amt}{unit}"
        item = QListWidgetItem(display)
        item.setData(Qt.ItemDataRole.UserRole, name)
        self.selected_list.addItem(item)

    def _on_selected_changed(self, current, previous):
        if current:
            name = current.data(Qt.ItemDataRole.UserRole)
            for ing in self.ingredients_list:
                if ing["item_name"] == name:
                    unit = ing.get("unit", "ea")
                    idx = self.unit_combo.findText(unit)
                    if idx >= 0:
                        self.unit_combo.setCurrentIndex(idx)
                    self._set_current_amount(ing.get("amount", 1))
                    self.nominal_cb.setChecked(ing.get("nominal", False))
                    break

    def on_set_qty(self):
        current = self.selected_list.currentItem()
        if not current:
            return

        name = current.data(Qt.ItemDataRole.UserRole)
        amount = self._get_current_amount()
        unit = self.unit_combo.currentText()
        nominal = self.nominal_cb.isChecked()

        for ing in self.ingredients_list:
            if ing["item_name"] == name:
                ing["amount"] = amount
                ing["unit"] = unit
                ing["nominal"] = nominal
                break

        if nominal:
            display = f"~ {name}"
        elif unit == "ea" and amount == 1:
            display = name
        else:
            amt = int(amount) if amount == int(amount) else amount
            display = f"{name}  —  {amt}{unit}"
        current.setText(display)

    def on_add_recipe(self):
        name = self.recipe_name.text().strip()
        servings = self.recipe_servings.value()
        tags = [t.strip() for t in self.recipe_tags.text().split(",") if t.strip()]
        instructions = self.recipe_instructions.toPlainText().strip()

        if not name:
            return

        if self._edit_name:
            r = Recipe()
            r.update(self._edit_name, "name", name)
            r.update(name, "servings", servings)
            r.update(name, "tags", tags)
            r.update(name, "ingredients", self.ingredients_list)
            r.update(name, "instructions", instructions)
        else:
            Recipe().create(name, servings, tags, self.ingredients_list, instructions)

        self.state.recipes_updated()

        # close parent dialog if present
        parent = self.parent()
        while parent:
            if hasattr(parent, 'accept'):
                parent.accept()
                break
            parent = parent.parent()

        self.recipe_name.clear()
        self.recipe_servings.setValue(1)
        self.recipe_tags.clear()
        self.recipe_instructions.clear()
        self.ingredients_list = []
        self.selected_list.clear()
