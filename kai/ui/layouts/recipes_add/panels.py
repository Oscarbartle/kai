from kai.ui import theme
from kai.ui.widgets.drag_lists import DragSourceList, DropTargetList

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QSpinBox, QDoubleSpinBox, QComboBox, QTextEdit,
    QStackedWidget, QCheckBox, QFrame,
)
from PySide6.QtGui import QCursor
from PySide6.QtCore import Qt


def _section_label(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet(theme.section_label_css())
    return lbl


def _divider() -> QFrame:
    line = QFrame()
    line.setFrameShape(QFrame.Shape.HLine)
    line.setStyleSheet(theme.divider_line_css())
    return line


class RecipeDetailsPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("recipe_left_panel")
        self.setStyleSheet(theme.inline_card_css("recipe_left_panel"))

        left_layout = QVBoxLayout(self)
        left_layout.setContentsMargins(16, 16, 16, 16)
        left_layout.setSpacing(12)

        left_layout.addWidget(_section_label("Recipe Details"))

        name_lbl = QLabel("Name")
        name_lbl.setProperty("role", "dim")
        left_layout.addWidget(name_lbl)
        self.recipe_name = QLineEdit()
        self.recipe_name.setPlaceholderText("Recipe name")
        self.recipe_name.setFixedHeight(34)
        left_layout.addWidget(self.recipe_name)

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
        left_layout.addWidget(_divider())

        left_layout.addWidget(_section_label("Instructions"))
        self.recipe_instructions = QTextEdit()
        self.recipe_instructions.setPlaceholderText("Write the recipe steps here…")
        left_layout.addWidget(self.recipe_instructions, 1)


class RecipeIngredientsPanel(QWidget):
    def __init__(self, on_drop_callback, parent=None):
        super().__init__(parent)
        t = theme.theme()

        self.setObjectName("recipe_right_panel")
        self.setStyleSheet(theme.inline_card_css("recipe_right_panel"))

        right_layout = QVBoxLayout(self)
        right_layout.setContentsMargins(16, 16, 16, 16)
        right_layout.setSpacing(10)

        right_layout.addWidget(_section_label("Ingredients"))

        search_row = QHBoxLayout()
        search_row.setSpacing(8)
        self.available_search = QLineEdit()
        self.available_search.setPlaceholderText("Search items…")
        self.available_search.setClearButtonEnabled(True)
        self.available_search.setFixedHeight(30)
        search_row.addWidget(self.available_search, 1)
        search_row.addSpacing(46)
        lbl_sel = QLabel("Recipe items")
        lbl_sel.setProperty("role", "faint")
        lbl_sel.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        search_row.addWidget(lbl_sel, 1)
        right_layout.addLayout(search_row)

        lists_row = QHBoxLayout()
        lists_row.setSpacing(0)

        self.available_list = DragSourceList()
        self.available_list.setMinimumWidth(160)
        lists_row.addWidget(self.available_list, 1)

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

        self.selected_list = DropTargetList(on_drop_callback=on_drop_callback)
        self.selected_list.setMinimumWidth(160)
        lists_row.addWidget(self.selected_list, 1)

        right_layout.addLayout(lists_row, 1)

        right_layout.addWidget(_divider())

        qty_label = _section_label("Set Amount  —  select an item above")
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

    def set_available_items(self, names: list[str]):
        self.available_list.clear()
        for name in names:
            self.available_list.addItem(name)
