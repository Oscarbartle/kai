from kai.objects.item import Item
from kai.objects.recipe import Recipe
from kai.ui import theme

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLineEdit, QLabel,
    QPushButton, QSpinBox, QDoubleSpinBox, QComboBox, QTextEdit, QHBoxLayout, QStyle, QStyleOption,
    QListWidget, QListWidgetItem, QAbstractItemView, QTabWidget, QStackedWidget
)
from PySide6.QtGui import QPainter, QDragEnterEvent, QDropEvent
from PySide6.QtCore import Qt, QMimeData


# ----- drag-drop list widgets ----- #

class DragSourceList(QListWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragEnabled(True)
        self.setDefaultDropAction(Qt.DropAction.CopyAction)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)

    def mimeData(self, items):
        mime = QMimeData()
        names = "\n".join(item.text() for item in items)
        mime.setText(names)
        return mime


class DropTargetList(QListWidget):
    def __init__(self, on_drop_callback=None, parent=None):
        super().__init__(parent)
        self.on_drop_callback = on_drop_callback
        self.setAcceptDrops(True)
        self.setDragEnabled(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasText():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if event.mimeData().hasText():
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event: QDropEvent):
        if event.source() == self:
            super().dropEvent(event)
            return
        if event.mimeData().hasText():
            names = event.mimeData().text().strip().split("\n")
            if self.on_drop_callback:
                self.on_drop_callback(names)
            event.acceptProposedAction()


class RecipesAdd(QWidget):
    def __init__(self, state, edit_recipe=None):
        super().__init__()

        self.state = state
        self.ingredients_list = []
        self._edit_name = edit_recipe  # recipe name to edit, or None for new

        self.layout = QVBoxLayout()
        self.layout.setContentsMargins(24, 20, 24, 20)
        self.layout.setSpacing(12)
        self.setLayout(self.layout)

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
        t = theme.theme()

        # ----- tab widget ----- #
        self.tabs = QTabWidget()
        self.tabs.setProperty("tab", "inner")

        # ----- tab 1: details ----- #
        self.details_tab = QWidget()
        details_layout = QVBoxLayout(self.details_tab)
        details_layout.setContentsMargins(16, 16, 16, 16)
        details_layout.setSpacing(14)

        name_label = QLabel("Name")
        name_label.setProperty("role", "dim")
        details_layout.addWidget(name_label)
        self.recipe_name = QLineEdit()
        self.recipe_name.setPlaceholderText("Recipe name")
        details_layout.addWidget(self.recipe_name)

        servings_row = QHBoxLayout()
        servings_row.setSpacing(12)
        servings_col = QVBoxLayout()
        servings_col.setSpacing(4)
        servings_label = QLabel("Servings")
        servings_label.setProperty("role", "dim")
        servings_col.addWidget(servings_label)
        self.recipe_servings = QSpinBox()
        self.recipe_servings.setMinimum(1)
        self.recipe_servings.setValue(1)
        self.recipe_servings.setFixedWidth(80)
        servings_col.addWidget(self.recipe_servings)
        servings_row.addLayout(servings_col)
        servings_row.addStretch()
        details_layout.addLayout(servings_row)

        tags_label = QLabel("Tags")
        tags_label.setProperty("role", "dim")
        details_layout.addWidget(tags_label)
        self.recipe_tags = QLineEdit()
        self.recipe_tags.setPlaceholderText("e.g. Dinner, Italian")
        details_layout.addWidget(self.recipe_tags)

        details_layout.addStretch()

        # ----- tab 2: ingredients ----- #
        self.ingredients_tab = QWidget()
        ing_layout = QVBoxLayout(self.ingredients_tab)
        ing_layout.setContentsMargins(12, 12, 12, 12)
        ing_layout.setSpacing(8)

        hint_label = QLabel("Drag items or use the arrow buttons. Double-click to add/remove.")
        hint_label.setProperty("role", "faint")
        hint_label.setWordWrap(True)
        ing_layout.addWidget(hint_label)

        picker_layout = QHBoxLayout()
        picker_layout.setSpacing(8)

        # left column: available
        left_col = QVBoxLayout()
        left_col.setSpacing(4)
        avail_label = QLabel("Available Items")
        avail_label.setProperty("role", "dim")
        left_col.addWidget(avail_label)

        self.available_search = QLineEdit()
        self.available_search.setPlaceholderText("Search items...")
        self.available_search.setClearButtonEnabled(True)
        left_col.addWidget(self.available_search)

        self.available_list = DragSourceList()
        self._refresh_item_list()
        left_col.addWidget(self.available_list, 1)

        # center column: transfer buttons
        center_col = QVBoxLayout()
        center_col.addStretch()

        self.add_ing_button = QPushButton(">")
        self.add_ing_button.setToolTip("Add selected items")
        self.add_ing_button.setFixedSize(34, 34)
        self.add_ing_button.setProperty("btn", "secondary")
        center_col.addWidget(self.add_ing_button)

        self.remove_ing_button = QPushButton("<")
        self.remove_ing_button.setToolTip("Remove selected items")
        self.remove_ing_button.setFixedSize(34, 34)
        self.remove_ing_button.setProperty("btn", "secondary")
        center_col.addWidget(self.remove_ing_button)

        center_col.addStretch()

        # right column: selected
        right_col = QVBoxLayout()
        right_col.setSpacing(4)
        sel_label = QLabel("Recipe Items")
        sel_label.setProperty("role", "dim")
        right_col.addWidget(sel_label)

        self.selected_list = DropTargetList(on_drop_callback=self._on_items_dropped)
        right_col.addWidget(self.selected_list, 1)

        # amount / unit row
        qty_row = QHBoxLayout()
        qty_row.setSpacing(8)

        self.amount_spin = QSpinBox()
        self.amount_spin.setMinimum(1)
        self.amount_spin.setMaximum(99999)
        self.amount_spin.setValue(1)
        self.amount_spin.setSingleStep(10)
        self.amount_spin.setFixedHeight(32)

        self.amount_spin_float = QDoubleSpinBox()
        self.amount_spin_float.setMinimum(0.1)
        self.amount_spin_float.setMaximum(9999)
        self.amount_spin_float.setValue(1.0)
        self.amount_spin_float.setDecimals(1)
        self.amount_spin_float.setSingleStep(0.1)
        self.amount_spin_float.setFixedHeight(32)

        self.amount_stack = QStackedWidget()
        self.amount_stack.addWidget(self.amount_spin)
        self.amount_stack.addWidget(self.amount_spin_float)
        self.amount_stack.setCurrentIndex(0)
        qty_row.addWidget(self.amount_stack, 1)

        self.unit_combo = QComboBox()
        self.unit_combo.addItems(["g", "kg", "mL", "L", "ea"])
        self.unit_combo.setFixedHeight(32)
        self.unit_combo.setMinimumWidth(58)
        qty_row.addWidget(self.unit_combo)

        self.set_qty_button = QPushButton("Set")
        self.set_qty_button.setFixedHeight(32)
        self.set_qty_button.setFixedWidth(48)
        self.set_qty_button.setProperty("btn", "secondary")
        qty_row.addWidget(self.set_qty_button)
        right_col.addLayout(qty_row)

        picker_layout.addLayout(left_col, 1)
        picker_layout.addLayout(center_col)
        picker_layout.addLayout(right_col, 1)

        ing_layout.addLayout(picker_layout, 1)

        # ----- tab 3: instructions ----- #
        self.instructions_tab = QWidget()
        inst_layout = QVBoxLayout(self.instructions_tab)
        inst_layout.setContentsMargins(12, 12, 12, 12)
        inst_layout.setSpacing(8)

        self.recipe_instructions = QTextEdit()
        self.recipe_instructions.setPlaceholderText("Write the recipe steps here...")
        inst_layout.addWidget(self.recipe_instructions, 1)

        # ----- add tabs ----- #
        self.tabs.addTab(self.details_tab, "Details")
        self.tabs.addTab(self.ingredients_tab, "Ingredients")
        self.tabs.addTab(self.instructions_tab, "Instructions")

        self.button = QPushButton("Save Changes" if self._edit_name else "Add Recipe")
        self.button.setProperty("btn", "primary")
        self.button.setFixedHeight(38)

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
            self.ingredients_list.append({"item_name": name, "amount": amount, "unit": unit})
            self._add_selected_display(name, amount, unit)

    def _refresh_item_list(self):
        self.available_list.clear()
        names = sorted(Item().get_item_names())
        for name in names:
            self.available_list.addItem(name)

    def add_layouts(self):
        self.layout.addWidget(self.tabs, 1)
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
                self.ingredients_list.append({"item_name": name, "amount": 1, "unit": "ea"})
                self._add_selected_display(name, 1, "ea")

    def on_add_ingredients(self):
        selected = self.available_list.selectedItems()
        for item in selected:
            name = item.text()
            if not self._ingredient_exists(name):
                self.ingredients_list.append({"item_name": name, "amount": 1, "unit": "ea"})
                self._add_selected_display(name, 1, "ea")

    def on_remove_ingredients(self):
        selected = self.selected_list.selectedItems()
        for item in selected:
            name = item.data(Qt.ItemDataRole.UserRole)
            self.ingredients_list = [i for i in self.ingredients_list if i["item_name"] != name]
            self.selected_list.takeItem(self.selected_list.row(item))

    def _on_available_double_click(self, item):
        name = item.text()
        if not self._ingredient_exists(name):
            self.ingredients_list.append({"item_name": name, "amount": 1, "unit": "ea"})
            self._add_selected_display(name, 1, "ea")

    def _on_selected_double_click(self, item):
        name = item.data(Qt.ItemDataRole.UserRole)
        self.ingredients_list = [i for i in self.ingredients_list if i["item_name"] != name]
        self.selected_list.takeItem(self.selected_list.row(item))

    def _ingredient_exists(self, name):
        return any(i["item_name"] == name for i in self.ingredients_list)

    def _add_selected_display(self, name, amount, unit):
        if unit == "ea" and amount == 1:
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
                    break

    def on_set_qty(self):
        current = self.selected_list.currentItem()
        if not current:
            return

        name = current.data(Qt.ItemDataRole.UserRole)
        amount = self._get_current_amount()
        unit = self.unit_combo.currentText()

        for ing in self.ingredients_list:
            if ing["item_name"] == name:
                ing["amount"] = amount
                ing["unit"] = unit
                break

        if unit == "ea" and amount == 1:
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
        self.tabs.setCurrentIndex(0)
