from kai.objects.item import Item
from kai.objects.recipe import Recipe
from kai.objects.shopping_list import ShoppingList
from kai.core.backend import get_recipe, get_shopping_list
from kai.ui import theme
from kai.utils.format_date import format_date
from kai.ui.tokens import (
    SPACE_SM, SPACE_MD,
    RADIUS_SM, RADIUS_MD, BORDER_W,
    H_CARD, H_FEATURE, H_ROW, H_ICON_BTN,
    FS_BODY, FS_META,
    FW_BOLD, FW_MEDIUM,
)

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QPushButton, QStyle, QStyleOption, QSpinBox,
)
from PySide6.QtGui import QPainter, QCursor, QIcon
from PySide6.QtCore import Qt, QSize
from pathlib import Path

_ICONS = Path(__file__).resolve().parent.parent.parent.parent / "icons"


class RecipePickerCard(QWidget):
    """Small recipe card with an Add button and multiplier."""

    def __init__(self, recipe_name, on_add):
        super().__init__()
        self._name = recipe_name
        self._on_add = on_add

        doc = get_recipe().get_recipe_details(recipe_name)
        if not doc:
            return

        self.tags = doc.get("tags", [])
        self.servings = doc.get("servings", 1)
        self.ingredients = doc.get("ingredients", [])
        self.cost, self.cost_full = self._calc_cost()

        self.setObjectName("recipe_pick_card")
        self.setMinimumHeight(H_FEATURE)
        self.setMaximumHeight(H_FEATURE)

        t = theme.theme()
        self.setStyleSheet(theme.inline_card_css("recipe_pick_card", radius=RADIUS_MD))

        layout = QGridLayout()
        layout.setContentsMargins(SPACE_MD, SPACE_SM, SPACE_MD, SPACE_SM)
        layout.setSpacing(4)
        self.setLayout(layout)

        name_label = QLabel(f"<b>{self._name}</b>")
        name_label.setStyleSheet(f"color: {t.text}; font-size: {FS_BODY}px;")
        layout.addWidget(name_label, 0, 0)

        tags_text = ", ".join(self.tags) if self.tags else ""
        if tags_text:
            tags_label = QLabel(f"<i>{tags_text}</i>")
            tags_label.setStyleSheet(
                f"color: {t.text_faint}; font-size: {FS_META}px; padding-left: 4px;"
            )
            layout.addWidget(tags_label, 0, 1)

        layout.setColumnStretch(1, 1)

        info_row = QHBoxLayout()
        info_row.setSpacing(SPACE_SM)

        cost_text = f"${self.cost:.2f}" if self.cost > 0 else "N/A"
        cost_label = QLabel(f"<b>{cost_text}</b>")
        cost_label.setStyleSheet(f"color: {t.accent}; font-size: {FS_BODY}px;")
        if self.cost > 0 and self.cost_full != self.cost:
            cost_label.setToolTip(f"${self.cost_full:.2f} including long-term items")
        info_row.addWidget(cost_label)

        ing_label = QLabel(f"{len(self.ingredients)} items")
        ing_label.setStyleSheet(f"color: {t.text_dim}; font-size: {FS_META}px;")
        info_row.addWidget(ing_label)

        serves_label = QLabel(f"Serves {self.servings}")
        serves_label.setStyleSheet(f"color: {t.text_dim}; font-size: {FS_META}px;")
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

        from kai.ui.widgets.nav_button import _colorize_svg
        _SIZE = 26
        t2 = theme.theme()
        add_btn = QPushButton()
        add_btn.setFixedSize(_SIZE, _SIZE)
        add_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        add_btn.setToolTip("Add to shopping list")
        add_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {t2.btn_bg};
                color: {t2.btn_fg};
                border: none;
                border-radius: {_SIZE // 2}px;
                min-width: {_SIZE}px;
                max-width: {_SIZE}px;
                min-height: {_SIZE}px;
                max-height: {_SIZE}px;
                padding: 0px;
            }}
            QPushButton:hover {{ background-color: {t2.btn_hover}; }}
            QPushButton:pressed {{ background-color: {t2.btn_pressed}; }}
        """)
        icon = _colorize_svg(str(_ICONS / "plus.svg"), t2.accent_fg, size=16)
        if icon:
            add_btn.setIcon(icon)
            add_btn.setIconSize(QSize(16, 16))
        else:
            add_btn.setText("+")
        add_btn.clicked.connect(self._on_click_add)
        right_col.addWidget(add_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        layout.addLayout(right_col, 0, 2, 2, 1)

    def _calc_cost(self):
        sl = get_shopping_list()
        entries = [{"recipe_name": self._name, "multiplier": 1}]
        try:
            items = sl.compute_items(entries, True)
            lt_items = sl.compute_long_term_items(entries)
        except NotImplementedError:
            return 0.0, 0.0
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
        self.setMinimumHeight(H_CARD)
        self.setMaximumHeight(H_CARD)

        t = theme.theme()
        self.setStyleSheet(theme.inline_card_css("saved_list_card", radius=RADIUS_MD))

        layout = QHBoxLayout()
        layout.setContentsMargins(SPACE_MD, SPACE_SM, SPACE_MD, SPACE_SM)
        layout.setSpacing(SPACE_SM)
        self.setLayout(layout)

        info_col = QVBoxLayout()
        info_col.setSpacing(2)

        name_label = QLabel(f"<b>{name}</b>")
        name_label.setStyleSheet(f"color: {t.text}; font-size: {FS_BODY}px;")
        name_label.setWordWrap(True)
        info_col.addWidget(name_label)

        date_text = format_date(date) if date else ""
        date_label = QLabel(date_text)
        date_label.setStyleSheet(f"color: {t.text_faint}; font-size: {FS_META}px;")
        info_col.addWidget(date_label)

        layout.addLayout(info_col, 1)

        load_btn = QPushButton("Open")
        load_btn.setProperty("btn", "secondary")
        load_btn.setFixedHeight(H_ROW)
        load_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        load_btn.clicked.connect(lambda: on_load(list_id))
        layout.addWidget(load_btn)

        del_btn = QPushButton("✕")
        del_btn.setFixedSize(H_ICON_BTN, H_ICON_BTN)
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
        self.setFixedHeight(H_ROW)

        t = theme.theme()
        self.setStyleSheet(theme.surface_row_css("cart_entry", radius=RADIUS_SM))

        layout = QHBoxLayout()
        layout.setContentsMargins(SPACE_SM, 0, 4, 0)
        layout.setSpacing(SPACE_SM)
        self.setLayout(layout)

        label = QLabel(recipe_name)
        label.setStyleSheet(f"color: {t.text}; font-size: {FS_BODY}px;")
        doc = get_recipe().get_recipe_details(recipe_name)
        base_servings = doc.get("servings", 1) if doc else 1
        total_servings = base_servings * multiplier
        label.setToolTip(f"Serves {total_servings}")
        layout.addWidget(label, 1)

        if multiplier > 1:
            count_badge = QLabel(f"{multiplier}")
            count_badge.setFixedSize(22, 22)
            count_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            count_badge.setStyleSheet(theme.badge_css(t.accent, t.accent_fg))
            layout.addWidget(count_badge)

        rm_btn = QPushButton("✕")
        rm_btn.setFixedSize(H_ICON_BTN, H_ICON_BTN)
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

    def __init__(self, item_name, units, on_remove, weight_kg=None):
        super().__init__()

        self.setObjectName("extra_item_entry")
        self.setFixedHeight(H_ROW)

        t = theme.theme()
        self.setStyleSheet(theme.surface_row_css("extra_item_entry", radius=RADIUS_SM))

        layout = QHBoxLayout()
        layout.setContentsMargins(SPACE_SM, 0, 4, 0)
        layout.setSpacing(SPACE_SM)
        self.setLayout(layout)

        label = QLabel(item_name)
        label.setStyleSheet(f"color: {t.text}; font-size: {FS_BODY}px;")
        layout.addWidget(label, 1)

        if weight_kg is not None:
            w = weight_kg
            w_str = f"{w:.2f} kg" if w != int(w) else f"{int(w)} kg"
            count_badge = QLabel(w_str)
            count_badge.setFixedHeight(22)
            count_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            count_badge.setStyleSheet(theme.badge_css(t.text_dim, t.bg))
            layout.addWidget(count_badge)
        elif units > 1:
            count_badge = QLabel(f"{units}")
            count_badge.setFixedSize(22, 22)
            count_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            count_badge.setStyleSheet(theme.badge_css(t.text_dim, t.bg))
            layout.addWidget(count_badge)

        rm_btn = QPushButton("✕")
        rm_btn.setFixedSize(H_ICON_BTN, H_ICON_BTN)
        rm_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        rm_btn.setStyleSheet(theme.remove_btn_css())
        rm_btn.clicked.connect(lambda: on_remove(item_name))
        layout.addWidget(rm_btn)

    def paintEvent(self, event):
        opt = QStyleOption()
        opt.initFrom(self)
        p = QPainter(self)
        self.style().drawPrimitive(QStyle.PE_Widget, opt, p, self)
