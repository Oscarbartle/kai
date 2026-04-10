from kai.objects.item import Item
from kai.objects.recipe import Recipe
from kai.objects.shopping_list import ShoppingList
from kai.ui import theme
from kai.utils.format_date import format_date

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QPushButton, QStyle, QStyleOption, QSpinBox,
)
from PySide6.QtGui import QPainter, QCursor
from PySide6.QtCore import Qt


class RecipePickerCard(QWidget):
    """Small recipe card with an Add button and multiplier."""

    def __init__(self, recipe_name, on_add):
        super().__init__()
        self._name = recipe_name
        self._on_add = on_add

        doc = Recipe().get_recipe_details(recipe_name)
        if not doc:
            return

        self.tags = doc.get("tags", [])
        self.servings = doc.get("servings", 1)
        self.ingredients = doc.get("ingredients", [])
        self.cost, self.cost_full = self._calc_cost()

        self.setObjectName("recipe_pick_card")
        self.setMinimumHeight(72)
        self.setMaximumHeight(72)

        t = theme.theme()
        self.setStyleSheet(theme.inline_card_css("recipe_pick_card", radius=8))

        layout = QGridLayout()
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(4)
        self.setLayout(layout)

        name_label = QLabel(f"<b>{self._name}</b>")
        name_label.setStyleSheet(f"color: {t.text}; font-size: 13px;")
        layout.addWidget(name_label, 0, 0)

        tags_text = ", ".join(self.tags) if self.tags else ""
        if tags_text:
            tags_label = QLabel(f"<i>{tags_text}</i>")
            tags_label.setStyleSheet(f"color: {t.text_faint}; font-size: 11px; padding-left: 4px;")
            layout.addWidget(tags_label, 0, 1)

        layout.setColumnStretch(1, 1)

        info_row = QHBoxLayout()
        info_row.setSpacing(10)

        cost_text = f"${self.cost}" if self.cost > 0 else "N/A"
        if self.cost > 0 and self.cost_full != self.cost:
            cost_text += f" <span style='color:{t.text_dim};font-size:11px;'>(${self.cost_full} w/LT)</span>"
        cost_label = QLabel(f"<b>{cost_text}</b>")
        cost_label.setStyleSheet(f"color: {t.accent}; font-size: 12px;")
        info_row.addWidget(cost_label)

        ing_label = QLabel(f"{len(self.ingredients)} items")
        ing_label.setStyleSheet(f"color: {t.text_dim}; font-size: 11px;")
        info_row.addWidget(ing_label)

        serves_label = QLabel(f"Serves {self.servings}")
        serves_label.setStyleSheet(f"color: {t.text_dim}; font-size: 11px;")
        info_row.addWidget(serves_label)

        info_row.addStretch()
        layout.addLayout(info_row, 1, 0, 1, 2)

        right_col = QVBoxLayout()
        right_col.setSpacing(4)
        right_col.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.mult_spin = QSpinBox()
        self.mult_spin.setMinimum(1)
        self.mult_spin.setMaximum(50)
        self.mult_spin.setValue(1)
        self.mult_spin.setFixedWidth(50)
        self.mult_spin.setToolTip("Multiplier")
        right_col.addWidget(self.mult_spin, alignment=Qt.AlignmentFlag.AlignCenter)

        add_btn = QPushButton("+ Add")
        add_btn.setFixedSize(50, 30)
        add_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        add_btn.setToolTip("Add to shopping list")
        add_btn.setStyleSheet(theme.mini_primary_btn_css())
        add_btn.clicked.connect(self._on_click_add)
        right_col.addWidget(add_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        layout.addLayout(right_col, 0, 2, 2, 1)

    def _calc_cost(self):
        sl = ShoppingList()
        entries = [{"recipe_name": self._name, "multiplier": 1}]
        items = sl.compute_items(entries, True)
        lt_items = sl.compute_long_term_items(entries)
        total = sum(it["price"] for it in items if it.get("price"))
        lt_total = sum(it["price"] for it in lt_items if it.get("price"))
        return round(total, 2), round(total + lt_total, 2)

    def _on_click_add(self):
        self._on_add(self._name, self.mult_spin.value())

    def paintEvent(self, event):
        opt = QStyleOption()
        opt.initFrom(self)
        p = QPainter(self)
        self.style().drawPrimitive(QStyle.PE_Widget, opt, p, self)


class SavedListCard(QWidget):
    """Card for a previously saved shopping list."""

    def __init__(self, name, list_id, date, on_load, on_delete):
        super().__init__()

        self.setObjectName("saved_list_card")
        self.setMinimumHeight(50)
        self.setMaximumHeight(50)

        t = theme.theme()
        self.setStyleSheet(theme.inline_card_css("saved_list_card", radius=8))

        layout = QHBoxLayout()
        layout.setContentsMargins(12, 6, 10, 6)
        layout.setSpacing(8)
        self.setLayout(layout)

        info_col = QVBoxLayout()
        info_col.setSpacing(2)

        name_label = QLabel(f"<b>{name}</b>")
        name_label.setStyleSheet(f"color: {t.text}; font-size: 12px;")
        name_label.setWordWrap(True)
        info_col.addWidget(name_label)

        date_text = format_date(date) if date else ""
        date_label = QLabel(date_text)
        date_label.setStyleSheet(f"color: {t.text_faint}; font-size: 10px;")
        info_col.addWidget(date_label)

        layout.addLayout(info_col, 1)

        load_btn = QPushButton("Open")
        load_btn.setProperty("btn", "secondary")
        load_btn.setFixedHeight(26)
        load_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        load_btn.clicked.connect(lambda: on_load(list_id))
        layout.addWidget(load_btn)

        del_btn = QPushButton("\u2715")
        del_btn.setFixedSize(22, 22)
        del_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        del_btn.setToolTip("Delete list")
        del_btn.setStyleSheet(theme.delete_btn_css())
        del_btn.clicked.connect(lambda: on_delete(list_id))
        layout.addWidget(del_btn)

    def paintEvent(self, event):
        opt = QStyleOption()
        opt.initFrom(self)
        p = QPainter(self)
        self.style().drawPrimitive(QStyle.PE_Widget, opt, p, self)


class CartEntry(QWidget):
    """Shows a recipe added to the cart with remove button."""

    def __init__(self, recipe_name, multiplier, on_remove):
        super().__init__()

        self.setObjectName("cart_entry")
        self.setFixedHeight(30)

        t = theme.theme()
        self.setStyleSheet(theme.surface_row_css("cart_entry"))

        layout = QHBoxLayout()
        layout.setContentsMargins(8, 2, 4, 2)
        layout.setSpacing(6)
        self.setLayout(layout)

        label = QLabel(recipe_name)
        label.setStyleSheet(f"color: {t.text}; font-size: 12px;")
        layout.addWidget(label, 1)

        doc = Recipe().get_recipe_details(recipe_name)
        base_servings = doc.get("servings", 1) if doc else 1
        total_servings = base_servings * multiplier
        serves_label = QLabel(f"Serves {total_servings}")
        serves_label.setStyleSheet(f"color: {t.text_dim}; font-size: 11px;")
        layout.addWidget(serves_label)

        if multiplier > 1:
            count_badge = QLabel(f"{multiplier}")
            count_badge.setFixedSize(22, 22)
            count_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            count_badge.setStyleSheet(theme.badge_css(t.accent, t.accent_fg))
            layout.addWidget(count_badge)

        rm_btn = QPushButton("\u2715")
        rm_btn.setFixedSize(18, 18)
        rm_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        rm_btn.setStyleSheet(theme.remove_btn_css())
        rm_btn.clicked.connect(lambda: on_remove(recipe_name))
        layout.addWidget(rm_btn)

    def paintEvent(self, event):
        opt = QStyleOption()
        opt.initFrom(self)
        p = QPainter(self)
        self.style().drawPrimitive(QStyle.PE_Widget, opt, p, self)


class ExtraItemEntry(QWidget):
    """Shows an individual item added to the cart with remove button."""

    def __init__(self, item_name, units, on_remove):
        super().__init__()

        self.setObjectName("extra_item_entry")
        self.setFixedHeight(30)

        t = theme.theme()
        self.setStyleSheet(theme.surface_row_css("extra_item_entry"))

        layout = QHBoxLayout()
        layout.setContentsMargins(8, 2, 4, 2)
        layout.setSpacing(6)
        self.setLayout(layout)

        label = QLabel(item_name)
        label.setStyleSheet(f"color: {t.text}; font-size: 12px;")
        layout.addWidget(label, 1)

        if units > 1:
            count_badge = QLabel(f"{units}")
            count_badge.setFixedSize(22, 22)
            count_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            count_badge.setStyleSheet(theme.badge_css(t.text_dim, t.bg))
            layout.addWidget(count_badge)

        rm_btn = QPushButton("\u2715")
        rm_btn.setFixedSize(18, 18)
        rm_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        rm_btn.setStyleSheet(theme.remove_btn_css())
        rm_btn.clicked.connect(lambda: on_remove(item_name))
        layout.addWidget(rm_btn)

    def paintEvent(self, event):
        opt = QStyleOption()
        opt.initFrom(self)
        p = QPainter(self)
        self.style().drawPrimitive(QStyle.PE_Widget, opt, p, self)
