from kai.objects.item import Item
from kai.objects.recipe import Recipe
from kai.ui import theme

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLineEdit, QLabel,
    QPushButton, QSpinBox, QDoubleSpinBox, QComboBox, QTextEdit, QHBoxLayout, QStyle, QStyleOption,
    QListWidget, QListWidgetItem, QAbstractItemView, QStackedWidget, QCheckBox, QFrame
)
from PySide6.QtGui import QPainter, QDragEnterEvent, QDropEvent, QCursor
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

    def _section_label(self, text: str) -> QLabel:
        t = theme.theme()
        lbl = QLabel(text)
        lbl.setStyleSheet(
            f"color: {t.text_dim}; font-size: 10px; font-weight: 700; "
            f"letter-spacing: 0.8px; text-transform: uppercase;"
        )
        return lbl

    def _divider(self) -> QFrame:
        t = theme.theme()
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet(f"background: {t.border}; border: none; max-height: 1px;")
        return line

    def create_widgets(self):
        t = theme.theme()

        # ── left panel: details + instructions ─────────────── #
        self.left_panel = QWidget()
        self.left_panel.setObjectName("recipe_left_panel")
        self.left_panel.setStyleSheet(f"""
            QWidget#recipe_left_panel {{
                background: {t.card};
                border: 1px solid {t.border};
                border-radius: 10px;
            }}
        """)
        left_layout = QVBoxLayout(self.left_panel)
        left_layout.setContentsMargins(16, 16, 16, 16)
        left_layout.setSpacing(12)

        left_layout.addWidget(self._section_label("Recipe Details"))

        # name
        name_lbl = QLabel("Name")
        name_lbl.setProperty("role", "dim")
        left_layout.addWidget(name_lbl)
        self.recipe_name = QLineEdit()
        self.recipe_name.setPlaceholderText("Recipe name")
        self.recipe_name.setFixedHeight(34)
        left_layout.addWidget(self.recipe_name)

        # servings + tags row
        meta_row = QHBoxLayout()
        meta_row.setSpacing(12)

        srv_col = QVBoxLayout()
        srv_col.setSpacing(4)
        srv_lbl = QLabel("Servings")
        srv_lbl.setProperty("role", "dim")
        srv_col.addWidget(srv_lbl)
        self.recipe_servings = QSpinBox()
        self.recipe_servings.setMinimum(1)
        self.recipe_servings.setValue(1)
        self.recipe_servings.setFixedHeight(34)
        self.recipe_servings.setFixedWidth(80)
        srv_col.addWidget(self.recipe_servings)
        meta_row.addLayout(srv_col)

        tags_col = QVBoxLayout()
        tags_col.setSpacing(4)
        tags_lbl = QLabel("Tags")
        tags_lbl.setProperty("role", "dim")
        tags_col.addWidget(tags_lbl)
        self.recipe_tags = QLineEdit()
        self.recipe_tags.setPlaceholderText("e.g. Dinner, Italian")
        self.recipe_tags.setFixedHeight(34)
        tags_col.addWidget(self.recipe_tags)
        meta_row.addLayout(tags_col, 1)

        left_layout.addLayout(meta_row)
        left_layout.addWidget(self._divider())

        left_layout.addWidget(self._section_label("Instructions"))
        self.recipe_instructions = QTextEdit()
        self.recipe_instructions.setPlaceholderText("Write the recipe steps here…")
        left_layout.addWidget(self.recipe_instructions, 1)

        # ── right panel: ingredients ────────────────────────── #
        self.right_panel = QWidget()
        self.right_panel.setObjectName("recipe_right_panel")
        self.right_panel.setStyleSheet(f"""
            QWidget#recipe_right_panel {{
                background: {t.card};
                border: 1px solid {t.border};
                border-radius: 10px;
            }}
        """)
        right_layout = QVBoxLayout(self.right_panel)
        right_layout.setContentsMargins(16, 16, 16, 16)
        right_layout.setSpacing(10)

        right_layout.addWidget(self._section_label("Ingredients"))

        # search bars row
        search_row = QHBoxLayout()
        search_row.setSpacing(8)
        self.available_search = QLineEdit()
        self.available_search.setPlaceholderText("Search items…")
        self.available_search.setClearButtonEnabled(True)
        self.available_search.setFixedHeight(30)
        search_row.addWidget(self.available_search, 1)
        search_row.addSpacing(46)  # aligns with transfer buttons gap
        lbl_sel = QLabel("Recipe items")
        lbl_sel.setProperty("role", "faint")
        lbl_sel.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        search_row.addWidget(lbl_sel, 1)
        right_layout.addLayout(search_row)

        # dual-list + transfer buttons
        lists_row = QHBoxLayout()
        lists_row.setSpacing(0)

        self.available_list = DragSourceList()
        self.available_list.setMinimumWidth(160)
        self._refresh_item_list()
        lists_row.addWidget(self.available_list, 1)

        # transfer button column
        btn_col = QVBoxLayout()
        btn_col.setContentsMargins(8, 0, 8, 0)
        btn_col.setSpacing(6)
        btn_col.addStretch()

        self.add_ing_button = QPushButton("›")
        self.add_ing_button.setToolTip("Add selected")
        self.add_ing_button.setFixedSize(30, 30)
        self.add_ing_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.add_ing_button.setStyleSheet(f"""
            QPushButton {{
                background: {t.surface};
                color: {t.text_dim};
                border: 1px solid {t.border};
                border-radius: 6px;
                font-size: 18px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background: {t.accent};
                color: {t.accent_fg};
                border-color: {t.accent};
            }}
        """)
        btn_col.addWidget(self.add_ing_button)

        self.remove_ing_button = QPushButton("‹")
        self.remove_ing_button.setToolTip("Remove selected")
        self.remove_ing_button.setFixedSize(30, 30)
        self.remove_ing_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.remove_ing_button.setStyleSheet(self.add_ing_button.styleSheet())
        btn_col.addWidget(self.remove_ing_button)
        btn_col.addStretch()
        lists_row.addLayout(btn_col)

        self.selected_list = DropTargetList(on_drop_callback=self._on_items_dropped)
        self.selected_list.setMinimumWidth(160)
        lists_row.addWidget(self.selected_list, 1)

        right_layout.addLayout(lists_row, 1)

        right_layout.addWidget(self._divider())

        # ── qty / nominal editor ──────────────────────────── #
        qty_label = self._section_label("Set Amount  —  select an item above")
        right_layout.addWidget(qty_label)

        qty_row = QHBoxLayout()
        qty_row.setSpacing(10)

        self.amount_spin = QSpinBox()
        self.amount_spin.setMinimum(1)
        self.amount_spin.setMaximum(99999)
        self.amount_spin.setValue(1)
        self.amount_spin.setSingleStep(10)
        self.amount_spin.setFixedHeight(34)

        self.amount_spin_float = QDoubleSpinBox()
        self.amount_spin_float.setMinimum(0.1)
        self.amount_spin_float.setMaximum(9999)
        self.amount_spin_float.setValue(1.0)
        self.amount_spin_float.setDecimals(1)
        self.amount_spin_float.setSingleStep(0.1)
        self.amount_spin_float.setFixedHeight(34)

        self.amount_stack = QStackedWidget()
        self.amount_stack.addWidget(self.amount_spin)
        self.amount_stack.addWidget(self.amount_spin_float)
        self.amount_stack.setCurrentIndex(0)
        self.amount_stack.setFixedHeight(34)
        qty_row.addWidget(self.amount_stack, 3)

        self.unit_combo = QComboBox()
        self.unit_combo.addItems(["g", "kg", "mL", "L", "ea"])
        self.unit_combo.setFixedHeight(34)
        self.unit_combo.setFixedWidth(72)
        qty_row.addWidget(self.unit_combo)

        self.nominal_cb = QCheckBox("Nominal")
        self.nominal_cb.setToolTip(
            "Use when an exact amount doesn't matter (e.g. olive oil, salt). "
            "Excluded from the recipe cost total; counted as 1 unit on shopping lists."
        )
        self.nominal_cb.setFixedHeight(34)
        qty_row.addWidget(self.nominal_cb)

        qty_row.addStretch(1)

        self.set_qty_button = QPushButton("Apply")
        self.set_qty_button.setFixedHeight(34)
        self.set_qty_button.setMinimumWidth(80)
        self.set_qty_button.setProperty("btn", "primary")
        self.set_qty_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        qty_row.addWidget(self.set_qty_button)

        right_layout.addLayout(qty_row)

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
        self.available_list.clear()
        names = sorted(Item().get_item_names())
        for name in names:
            self.available_list.addItem(name)

    def add_layouts(self):
        # apply stylesheet helpers to inner widgets
        input_style = theme.input_css()
        list_style = theme.list_widget_css()
        cb_style = theme.checkbox_css()

        for w in (self.recipe_name, self.recipe_tags, self.available_search,
                  self.recipe_servings, self.unit_combo,
                  self.amount_spin, self.amount_spin_float):
            w.setStyleSheet(input_style)
        self.recipe_instructions.setStyleSheet(input_style)

        self.available_list.setStyleSheet(list_style)
        self.selected_list.setStyleSheet(list_style)
        self.nominal_cb.setStyleSheet(cb_style)
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
