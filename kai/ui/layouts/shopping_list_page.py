from kai.objects.recipe import Recipe
from kai.objects.item import Item
from kai.objects.shopping_list import ShoppingList
from ..widgets.shopping_item import ShoppingItem
from kai.ui import theme
from kai.ui.refresh_worker import run_refresh
from kai.utils.format_date import format_date
from kai.core import settings as app_settings

import webbrowser
import json
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QComboBox,
    QPushButton, QCheckBox, QScrollArea, QStyle, QStyleOption,
    QApplication, QSpinBox, QStackedWidget, QLineEdit, QSizePolicy, QSplitter, QSplitterHandle
)
from PySide6.QtGui import QPainter, QCursor, QColor
from PySide6.QtCore import Qt, QRect


# ── styled splitter ───────────────────────────────────────────── #

class _SplitterHandle(QSplitterHandle):
    def __init__(self, orientation, parent):
        super().__init__(orientation, parent)
        self._hovered = False
        self.setMouseTracking(True)

    def enterEvent(self, event):
        self._hovered = True
        self.update()

    def leaveEvent(self, event):
        self._hovered = False
        self.update()

    def paintEvent(self, event):
        t = theme.theme()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        pill_w, pill_h = 32, 3
        cx = self.width() // 2
        cy = self.height() // 2
        rect = QRect(cx - pill_w // 2, cy - pill_h // 2, pill_w, pill_h)
        p.setPen(Qt.PenStyle.NoPen)
        color = QColor(t.accent) if self._hovered else QColor(t.border)
        p.setBrush(color)
        p.drawRoundedRect(rect, pill_h // 2, pill_h // 2)


class StyledSplitter(QSplitter):
    def createHandle(self):
        return _SplitterHandle(self.orientation(), self)


# ── collapsible section ────────────────────────────────────────── #

class CollapsibleSection(QWidget):
    """A section with a clickable header that collapses/expands its content."""

    def __init__(self, title, parent=None, collapsed=False):
        super().__init__(parent)
        t = theme.theme()

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.setLayout(layout)

        # header button
        self._collapsed = collapsed
        self._arrow_right = "\u25b6"
        self._arrow_down = "\u25bc"

        self.toggle_btn = QPushButton(f"  {self._arrow_down if not collapsed else self._arrow_right}  {title}")
        self.toggle_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.toggle_btn.setFixedHeight(32)
        self.toggle_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {t.surface};
                color: {t.text};
                border: none;
                border-radius: 6px;
                font-size: 12px;
                font-weight: bold;
                text-align: left;
                padding-left: 4px;
            }}
            QPushButton:hover {{
                background-color: {t.border};
            }}
        """)
        self.toggle_btn.clicked.connect(self._toggle)
        layout.addWidget(self.toggle_btn)

        # content area
        self.content = QWidget()
        self.content.setStyleSheet("background: transparent;")
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(0, 6, 0, 0)
        self.content_layout.setSpacing(4)
        layout.addWidget(self.content)

        if collapsed:
            self.content.setVisible(False)

        self._title = title

    def _toggle(self):
        self._collapsed = not self._collapsed
        self.content.setVisible(not self._collapsed)
        arrow = self._arrow_right if self._collapsed else self._arrow_down
        self.toggle_btn.setText(f"  {arrow}  {self._title}")

    def paintEvent(self, event):
        opt = QStyleOption()
        opt.initFrom(self)
        p = QPainter(self)
        self.style().drawPrimitive(QStyle.PE_Widget, opt, p, self)


# ── compact recipe card for the picker ─────────────────────────── #

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
        self.setStyleSheet(f"""
            QWidget#recipe_pick_card {{
                background-color: {t.card};
                border-radius: 8px;
                border: 1px solid {t.border};
            }}
        """)

        layout = QGridLayout()
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(4)
        self.setLayout(layout)

        name_label = QLabel(f"<b>{recipe_name}</b>")
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

        # right side: multiplier + add
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
        add_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {t.btn_bg};
                color: {t.btn_fg};
                border: none;
                border-radius: 6px;
                font-size: 13px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {t.btn_hover};
            }}
            QPushButton:pressed {{
                background-color: {t.btn_pressed};
            }}
        """)
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


# ── saved list card ────────────────────────────────────────────── #

class SavedListCard(QWidget):
    """Card for a previously saved shopping list."""

    def __init__(self, name, list_id, date, on_load, on_delete):
        super().__init__()
        self._list_id = list_id

        self.setObjectName("saved_list_card")
        self.setMinimumHeight(50)
        self.setMaximumHeight(50)

        t = theme.theme()
        self.setStyleSheet(f"""
            QWidget#saved_list_card {{
                background-color: {t.card};
                border-radius: 8px;
                border: 1px solid {t.border};
            }}
        """)

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
        del_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {t.text_faint};
                border: none; font-size: 13px; font-weight: bold;
            }}
            QPushButton:hover {{ color: {t.danger}; background: {t.danger}22; border-radius: 4px; }}
        """)
        del_btn.clicked.connect(lambda: on_delete(list_id))
        layout.addWidget(del_btn)

    def paintEvent(self, event):
        opt = QStyleOption()
        opt.initFrom(self)
        p = QPainter(self)
        self.style().drawPrimitive(QStyle.PE_Widget, opt, p, self)


# ── cart entry (recipe added to the list) ──────────────────────── #

class CartEntry(QWidget):
    """Shows a recipe added to the cart with remove button."""

    def __init__(self, recipe_name, multiplier, on_remove):
        super().__init__()
        self._name = recipe_name

        self.setObjectName("cart_entry")
        self.setFixedHeight(30)

        t = theme.theme()
        self.setStyleSheet(f"""
            QWidget#cart_entry {{
                background-color: {t.surface};
                border-radius: 6px;
                border: 1px solid {t.border};
            }}
        """)

        layout = QHBoxLayout()
        layout.setContentsMargins(8, 2, 4, 2)
        layout.setSpacing(6)
        self.setLayout(layout)

        # recipe name
        label = QLabel(recipe_name)
        label.setStyleSheet(f"color: {t.text}; font-size: 12px;")
        layout.addWidget(label, 1)

        # serves info
        doc = Recipe().get_recipe_details(recipe_name)
        base_servings = doc.get("servings", 1) if doc else 1
        total_servings = base_servings * multiplier
        serves_label = QLabel(f"Serves {total_servings}")
        serves_label.setStyleSheet(f"color: {t.text_dim}; font-size: 11px;")
        layout.addWidget(serves_label)

        # multiplier badge
        if multiplier > 1:
            count_badge = QLabel(f"{multiplier}")
            count_badge.setFixedSize(22, 22)
            count_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            count_badge.setStyleSheet(f"""
                background-color: {t.accent};
                color: {t.accent_fg};
                border-radius: 11px;
                font-size: 11px;
                font-weight: bold;
            """)
            layout.addWidget(count_badge)

        rm_btn = QPushButton("\u2715")
        rm_btn.setFixedSize(18, 18)
        rm_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        rm_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {t.text_faint};
                border: none; font-size: 11px;
            }}
            QPushButton:hover {{ color: {t.danger}; }}
        """)
        rm_btn.clicked.connect(lambda: on_remove(recipe_name))
        layout.addWidget(rm_btn)

    def paintEvent(self, event):
        opt = QStyleOption()
        opt.initFrom(self)
        p = QPainter(self)
        self.style().drawPrimitive(QStyle.PE_Widget, opt, p, self)


# ── extra item entry (individual item added to the list) ───────── #

class ExtraItemEntry(QWidget):
    """Shows an individual item added to the cart with remove button."""

    def __init__(self, item_name, units, on_remove):
        super().__init__()
        self._name = item_name

        self.setObjectName("extra_item_entry")
        self.setFixedHeight(30)

        t = theme.theme()
        self.setStyleSheet(f"""
            QWidget#extra_item_entry {{
                background-color: {t.surface};
                border-radius: 6px;
                border: 1px solid {t.border};
            }}
        """)

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
            count_badge.setStyleSheet(f"""
                background-color: {t.text_dim};
                color: {t.bg};
                border-radius: 11px;
                font-size: 11px;
                font-weight: bold;
            """)
            layout.addWidget(count_badge)

        rm_btn = QPushButton("\u2715")
        rm_btn.setFixedSize(18, 18)
        rm_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        rm_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {t.text_faint};
                border: none; font-size: 11px;
            }}
            QPushButton:hover {{ color: {t.danger}; }}
        """)
        rm_btn.clicked.connect(lambda: on_remove(item_name))
        layout.addWidget(rm_btn)

    def paintEvent(self, event):
        opt = QStyleOption()
        opt.initFrom(self)
        p = QPainter(self)
        self.style().drawPrimitive(QStyle.PE_Widget, opt, p, self)


# ── main page ──────────────────────────────────────────────────── #

class ShoppingListPage(QWidget):
    def __init__(self, state):
        super().__init__()

        self.state = state
        self.current_list_id = None
        self.recipe_entries = []
        self.extra_items = []  # [{"item_name": str, "units": int}]
        self.preview_items = []
        self.lt_items = []  # long-term items needed
        self.lt_have = {}  # {item_name: bool} — True = I have it

        self.layout = QGridLayout()
        self.layout.setContentsMargins(8, 8, 8, 8)
        self.layout.setSpacing(8)
        self.layout.setColumnStretch(0, 2)
        self.layout.setColumnStretch(1, 3)
        self.setLayout(self.layout)

        self._build_left_panel()
        self._build_right_panel()
        self.connections()
        self._load_draft()

    def paintEvent(self, event):
        opt = QStyleOption()
        opt.initFrom(self)
        p = QPainter(self)
        self.style().drawPrimitive(QStyle.PE_Widget, opt, p, self)

    # ── left panel: recipe picker + item picker + saved lists ── #

    def _build_left_panel(self):
        self.left_panel = QWidget()
        self.left_panel.setObjectName("page_panel")
        left_layout = QVBoxLayout(self.left_panel)
        left_layout.setContentsMargins(12, 12, 12, 12)
        left_layout.setSpacing(8)

        self.left_stack = QStackedWidget()

        # --- page 0: recipe picker --- #
        self.picker_page = QWidget()
        picker_layout = QVBoxLayout(self.picker_page)
        picker_layout.setContentsMargins(0, 0, 0, 0)
        picker_layout.setSpacing(8)

        header = QHBoxLayout()
        recipes_label = QLabel("Recipes")
        recipes_label.setProperty("role", "heading")
        header.addWidget(recipes_label)
        header.addStretch()

        self.show_items_btn = QPushButton("Items")
        self.show_items_btn.setProperty("btn", "secondary")
        self.show_items_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        header.addWidget(self.show_items_btn)

        self.show_saved_btn = QPushButton("Saved Lists")
        self.show_saved_btn.setProperty("btn", "secondary")
        self.show_saved_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        header.addWidget(self.show_saved_btn)
        picker_layout.addLayout(header)

        # search
        self.recipe_search = QLineEdit()
        self.recipe_search.setPlaceholderText("Search recipes...")
        self.recipe_search.setClearButtonEnabled(True)
        self.recipe_search.setFixedHeight(30)
        picker_layout.addWidget(self.recipe_search)

        # tag filter
        t = theme.theme()
        self.tag_scroll = QScrollArea()
        self.tag_scroll.setWidgetResizable(True)
        self.tag_scroll.setFixedHeight(34)
        self.tag_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.tag_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.tag_scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        self.tag_bar_widget = QWidget()
        self.tag_bar_widget.setStyleSheet("background: transparent;")
        self.tag_bar_layout = QHBoxLayout(self.tag_bar_widget)
        self.tag_bar_layout.setContentsMargins(0, 0, 0, 0)
        self.tag_bar_layout.setSpacing(4)
        self.tag_bar_layout.addStretch()
        self.tag_scroll.setWidget(self.tag_bar_widget)
        picker_layout.addWidget(self.tag_scroll)

        self._active_tag = None
        self._recipe_cards = []

        self.recipe_scroll = QScrollArea()
        self.recipe_scroll.setWidgetResizable(True)
        self.recipe_scroll_widget = QWidget()
        self.recipe_scroll_widget.setStyleSheet("background: transparent;")
        self.recipe_scroll_layout = QVBoxLayout(self.recipe_scroll_widget)
        self.recipe_scroll_layout.setContentsMargins(2, 2, 2, 2)
        self.recipe_scroll_layout.setSpacing(6)
        self.recipe_scroll.setWidget(self.recipe_scroll_widget)
        picker_layout.addWidget(self.recipe_scroll, 1)

        self.left_stack.addWidget(self.picker_page)

        # --- page 1: saved lists --- #
        self.saved_page = QWidget()
        saved_layout = QVBoxLayout(self.saved_page)
        saved_layout.setContentsMargins(0, 0, 0, 0)
        saved_layout.setSpacing(8)

        saved_header = QHBoxLayout()
        saved_label = QLabel("Saved Lists")
        saved_label.setProperty("role", "heading")
        saved_header.addWidget(saved_label)
        saved_header.addStretch()

        self.back_to_recipes_btn = QPushButton("Back")
        self.back_to_recipes_btn.setProperty("btn", "secondary")
        self.back_to_recipes_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        saved_header.addWidget(self.back_to_recipes_btn)
        saved_layout.addLayout(saved_header)

        self.saved_scroll = QScrollArea()
        self.saved_scroll.setWidgetResizable(True)
        self.saved_scroll_widget = QWidget()
        self.saved_scroll_widget.setStyleSheet("background: transparent;")
        self.saved_scroll_layout = QVBoxLayout(self.saved_scroll_widget)
        self.saved_scroll_layout.setContentsMargins(2, 2, 2, 2)
        self.saved_scroll_layout.setSpacing(6)
        self.saved_scroll.setWidget(self.saved_scroll_widget)
        saved_layout.addWidget(self.saved_scroll, 1)

        self.left_stack.addWidget(self.saved_page)

        # --- page 2: item picker --- #
        self.item_picker_page = QWidget()
        item_picker_layout = QVBoxLayout(self.item_picker_page)
        item_picker_layout.setContentsMargins(0, 0, 0, 0)
        item_picker_layout.setSpacing(8)

        item_header = QHBoxLayout()
        items_label = QLabel("Items")
        items_label.setProperty("role", "heading")
        item_header.addWidget(items_label)
        item_header.addStretch()

        self.back_to_recipes_btn2 = QPushButton("Back")
        self.back_to_recipes_btn2.setProperty("btn", "secondary")
        self.back_to_recipes_btn2.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        item_header.addWidget(self.back_to_recipes_btn2)
        item_picker_layout.addLayout(item_header)

        self.item_search = QLineEdit()
        self.item_search.setPlaceholderText("Search items...")
        self.item_search.setClearButtonEnabled(True)
        self.item_search.setFixedHeight(30)
        item_picker_layout.addWidget(self.item_search)

        # item tag filter
        self.item_tag_scroll = QScrollArea()
        self.item_tag_scroll.setWidgetResizable(True)
        self.item_tag_scroll.setFixedHeight(34)
        self.item_tag_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.item_tag_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.item_tag_scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        self.item_tag_bar_widget = QWidget()
        self.item_tag_bar_widget.setStyleSheet("background: transparent;")
        self.item_tag_bar_layout = QHBoxLayout(self.item_tag_bar_widget)
        self.item_tag_bar_layout.setContentsMargins(0, 0, 0, 0)
        self.item_tag_bar_layout.setSpacing(4)
        self.item_tag_bar_layout.addStretch()
        self.item_tag_scroll.setWidget(self.item_tag_bar_widget)
        item_picker_layout.addWidget(self.item_tag_scroll)

        self._active_item_tag = None

        self.item_scroll = QScrollArea()
        self.item_scroll.setWidgetResizable(True)
        self.item_scroll_widget = QWidget()
        self.item_scroll_widget.setStyleSheet("background: transparent;")
        self.item_scroll_layout = QVBoxLayout(self.item_scroll_widget)
        self.item_scroll_layout.setContentsMargins(2, 2, 2, 2)
        self.item_scroll_layout.setSpacing(4)
        self.item_scroll.setWidget(self.item_scroll_widget)
        item_picker_layout.addWidget(self.item_scroll, 1)

        self.left_stack.addWidget(self.item_picker_page)
        self._item_rows = []

        left_layout.addWidget(self.left_stack)

        self.layout.addWidget(self.left_panel, 0, 0)

        self._refresh_recipe_cards()

    # ── right panel: cart + generated list ─────────────────────── #

    def _build_right_panel(self):
        self.right_panel = QWidget()
        self.right_panel.setObjectName("page_panel")
        right_layout = QVBoxLayout(self.right_panel)
        right_layout.setContentsMargins(16, 16, 16, 16)
        right_layout.setSpacing(12)

        t = theme.theme()

        # ── page heading + name/copy row ──
        cart_label = QLabel("Shopping List")
        cart_label.setProperty("role", "heading")
        right_layout.addWidget(cart_label)

        top_row = QHBoxLayout()
        top_row.setSpacing(8)

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("List name (optional)")
        self.name_input.setFixedHeight(30)
        top_row.addWidget(self.name_input, 1)

        self.save_button = QPushButton("Save List")
        self.save_button.setProperty("btn", "primary")
        self.save_button.setFixedHeight(30)
        self.save_button.setEnabled(False)
        top_row.addWidget(self.save_button)

        self.export_button = QPushButton("Copy")
        self.export_button.setProperty("btn", "secondary")
        self.export_button.setFixedHeight(30)
        self.export_button.setToolTip("Copy list to clipboard")
        self.export_button.setEnabled(False)
        top_row.addWidget(self.export_button)

        self.links_button = QPushButton("Links")
        self.links_button.setProperty("btn", "secondary")
        self.links_button.setFixedHeight(30)
        self.links_button.setEnabled(False)
        self.links_button.setToolTip("Copy Woolworths links for all items")
        top_row.addWidget(self.links_button)

        right_layout.addLayout(top_row)

        # ── Items header + totals ──
        items_header = QHBoxLayout()
        items_heading = QLabel("Items")
        items_heading.setStyleSheet(f"color: {t.text}; font-size: 13px; font-weight: bold;")
        items_header.addWidget(items_heading)
        items_header.addStretch()

        self.serves_label = QLabel("")
        self.serves_label.setStyleSheet(f"color: {t.text_dim}; font-size: 12px;")
        items_header.addWidget(self.serves_label)

        self.count_label = QLabel("")
        self.count_label.setProperty("role", "dim")
        items_header.addWidget(self.count_label)

        self.total_label = QLabel("")
        self.total_label.setProperty("role", "price")
        items_header.addWidget(self.total_label)
        right_layout.addLayout(items_header)

        sep = QWidget()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background-color: {t.border};")
        right_layout.addWidget(sep)

        # ── Splitter: items list (top) + cart/LT (bottom) ──
        self.right_splitter = StyledSplitter(Qt.Orientation.Vertical)
        self.right_splitter.setHandleWidth(16)

        # top pane: scrollable items list
        self.items_scroll = QScrollArea()
        self.items_scroll.setWidgetResizable(True)
        self.items_scroll.setStyleSheet("QScrollArea { border: none; }")
        items_scroll_widget = QWidget()
        items_scroll_widget.setStyleSheet("background: transparent;")
        self.items_scroll_layout = QVBoxLayout(items_scroll_widget)
        self.items_scroll_layout.setContentsMargins(0, 4, 0, 4)
        self.items_scroll_layout.setSpacing(4)
        self.items_scroll_layout.addStretch()
        self.items_scroll.setWidget(items_scroll_widget)
        self.right_splitter.addWidget(self.items_scroll)

        # bottom pane: Cart + Long-term Items
        self.bottom_scroll = QScrollArea()
        self.bottom_scroll.setWidgetResizable(True)
        self.bottom_scroll.setStyleSheet("QScrollArea { border: none; }")
        bottom_scroll_widget = QWidget()
        bottom_scroll_widget.setStyleSheet("background: transparent;")
        bottom_scroll_layout = QVBoxLayout(bottom_scroll_widget)
        bottom_scroll_layout.setContentsMargins(0, 0, 0, 0)
        bottom_scroll_layout.setSpacing(6)

        # ── Collapsible: Cart ──
        self.cart_section = CollapsibleSection("Cart", collapsed=True)
        self.cart_layout = self.cart_section.content_layout

        self.empty_cart_label = QLabel("Add recipes or items to get started")
        self.empty_cart_label.setProperty("role", "faint")
        self.cart_layout.addWidget(self.empty_cart_label)

        bottom_scroll_layout.addWidget(self.cart_section)

        # ── Collapsible: Long-term Items ──
        self.lt_section = CollapsibleSection("Long-term Items", collapsed=True)
        self.lt_layout = self.lt_section.content_layout

        self.lt_empty_label = QLabel("No long-term items needed")
        self.lt_empty_label.setProperty("role", "faint")
        self.lt_layout.addWidget(self.lt_empty_label)

        bottom_scroll_layout.addWidget(self.lt_section)
        bottom_scroll_layout.addStretch()

        self.bottom_scroll.setWidget(bottom_scroll_widget)
        self.right_splitter.addWidget(self.bottom_scroll)

        # default sizes: give items list most of the space
        self.right_splitter.setSizes([9999, 220])

        right_layout.addWidget(self.right_splitter, 1)

        self.layout.addWidget(self.right_panel, 0, 1)

    # ── connections ────────────────────────────────────────────── #

    def connections(self):
        self.export_button.clicked.connect(self._on_export)
        self.links_button.clicked.connect(self._on_links)
        self.save_button.clicked.connect(self._on_save)
        self.show_saved_btn.clicked.connect(self._show_saved_lists)
        self.back_to_recipes_btn.clicked.connect(self._show_recipes)
        self.show_items_btn.clicked.connect(self._show_item_picker)
        self.back_to_recipes_btn2.clicked.connect(self._show_recipes)
        self.item_search.textChanged.connect(self._filter_item_rows)
        self.state.new_recipes.connect(self._refresh_recipe_cards)
        self.state.new_items.connect(self._refresh_item_rows)
        self.recipe_search.textChanged.connect(self._filter_recipe_cards)

    # ── recipe picker ──────────────────────────────────────────── #

    def _refresh_recipe_cards(self):
        while self.recipe_scroll_layout.count():
            child = self.recipe_scroll_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        self._recipe_cards = []
        recipes = Recipe().get_recipes()
        recipes.sort(key=lambda x: x[0])

        if not recipes:
            empty = QLabel("No recipes yet \u2014 create some first!")
            empty.setProperty("role", "faint")
            self.recipe_scroll_layout.addWidget(empty)
        else:
            for name, _ in recipes:
                card = RecipePickerCard(name, self._add_recipe_to_cart)
                self._recipe_cards.append(card)
                self.recipe_scroll_layout.addWidget(card)

        self.recipe_scroll_layout.addStretch()
        self._refresh_tag_bar()
        self._active_tag = None
        self.recipe_search.clear()

    def _refresh_tag_bar(self):
        """Rebuild tag filter chips from current recipe tags."""
        while self.tag_bar_layout.count():
            child = self.tag_bar_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        t = theme.theme()
        tags = sorted(Recipe().get_recipe_tags())

        if not tags:
            self.tag_scroll.setVisible(False)
            return

        self.tag_scroll.setVisible(True)

        # Favourites chip first
        fav_btn = QPushButton("★ Favourites")
        fav_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        fav_btn.setCheckable(True)
        fav_btn.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        fav_btn.setFixedHeight(26)
        fav_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {t.surface};
                color: {t.text_dim};
                border: 1px solid {t.border};
                border-radius: 13px;
                padding: 0 12px;
                font-size: 11px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {t.border};
                color: {t.text};
            }}
            QPushButton:checked {{
                background-color: {t.accent};
                color: {t.accent_fg};
                border-color: {t.accent};
            }}
        """)
        fav_btn.clicked.connect(lambda checked: self._on_tag_clicked("★ Favourites", checked))
        self.tag_bar_layout.addWidget(fav_btn)

        for tag in tags:
            btn = QPushButton(tag)
            btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            btn.setCheckable(True)
            btn.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
            btn.setFixedHeight(26)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {t.surface};
                    color: {t.text_dim};
                    border: 1px solid {t.border};
                    border-radius: 13px;
                    padding: 0 12px;
                    font-size: 11px;
                    font-weight: 600;
                }}
                QPushButton:hover {{
                    background-color: {t.border};
                    color: {t.text};
                }}
                QPushButton:checked {{
                    background-color: {t.accent};
                    color: {t.accent_fg};
                    border-color: {t.accent};
                }}
            """)
            btn.clicked.connect(lambda checked, tg=tag: self._on_tag_clicked(tg, checked))
            self.tag_bar_layout.addWidget(btn)

        self.tag_bar_layout.addStretch()

    def _on_tag_clicked(self, tag, checked):
        if checked:
            self._active_tag = tag
        else:
            self._active_tag = None

        # uncheck other tag buttons
        for i in range(self.tag_bar_layout.count()):
            w = self.tag_bar_layout.itemAt(i).widget()
            if w and isinstance(w, QPushButton) and w.text() != tag:
                w.setChecked(False)

        self._filter_recipe_cards()

    def _filter_recipe_cards(self, _text=None):
        search = self.recipe_search.text().lower().strip()
        for card in self._recipe_cards:
            name_match = not search or search in card._name.lower()
            if self._active_tag == "★ Favourites":
                doc = Recipe().get_recipe_details(card._name)
                tag_match = doc.get("is_favourite", False) if doc else False
            else:
                tag_match = not self._active_tag or self._active_tag in card.tags
            card.setVisible(name_match and tag_match)

    # ── item picker ────────────────────────────────────────────── #

    def _show_item_picker(self):
        self._refresh_item_rows()
        self.left_stack.setCurrentIndex(2)

    def _refresh_item_rows(self):
        while self.item_scroll_layout.count():
            child = self.item_scroll_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        self._item_rows = []
        t = theme.theme()
        item_obj = Item()
        names = sorted(item_obj.get_item_names())

        for name in names:
            row = QWidget()
            row.setObjectName("item_pick_row")
            row.setFixedHeight(38)
            row.setStyleSheet(f"""
                QWidget#item_pick_row {{
                    background-color: {t.card};
                    border-radius: 6px;
                    border: 1px solid {t.border};
                }}
            """)
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(10, 4, 6, 4)
            row_layout.setSpacing(6)

            label = QLabel(name)
            label.setStyleSheet(f"color: {t.text}; font-size: 12px;")
            row_layout.addWidget(label, 1)

            spin = QSpinBox()
            spin.setMinimum(1)
            spin.setMaximum(99)
            spin.setValue(1)
            spin.setFixedWidth(50)
            spin.setFixedHeight(26)
            row_layout.addWidget(spin)

            add_btn = QPushButton("+")
            add_btn.setFixedSize(28, 28)
            add_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            add_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {t.btn_bg};
                    color: {t.btn_fg};
                    border: none;
                    border-radius: 14px;
                    font-size: 16px;
                    font-weight: bold;
                }}
                QPushButton:hover {{
                    background-color: {t.btn_hover};
                }}
                QPushButton:pressed {{
                    background-color: {t.btn_pressed};
                }}
            """)
            add_btn.clicked.connect(lambda checked, n=name, s=spin: self._add_extra_item(n, s.value()))
            row_layout.addWidget(add_btn)

            row._item_name = name
            details = item_obj.get_item_details(name)
            row._item_tags = details.get("tags", []) if details else []
            self._item_rows.append(row)
            self.item_scroll_layout.addWidget(row)

        self.item_scroll_layout.addStretch()
        self._refresh_item_tag_bar()

    def _filter_item_rows(self, _text=None):
        search = self.item_search.text().lower().strip()
        for row in self._item_rows:
            name_match = not search or search in row._item_name.lower()
            tag_match = not self._active_item_tag or self._active_item_tag in row._item_tags
            row.setVisible(name_match and tag_match)

    def _refresh_item_tag_bar(self):
        """Rebuild tag filter chips from current item tags."""
        while self.item_tag_bar_layout.count():
            child = self.item_tag_bar_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        t = theme.theme()
        tags = sorted(Item().get_item_tags())

        if not tags:
            self.item_tag_scroll.setVisible(False)
            return

        self.item_tag_scroll.setVisible(True)
        for tag in tags:
            btn = QPushButton(tag)
            btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            btn.setCheckable(True)
            btn.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
            btn.setFixedHeight(26)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {t.surface};
                    color: {t.text_dim};
                    border: 1px solid {t.border};
                    border-radius: 13px;
                    padding: 0 12px;
                    font-size: 11px;
                    font-weight: 600;
                }}
                QPushButton:hover {{
                    background-color: {t.border};
                    color: {t.text};
                }}
                QPushButton:checked {{
                    background-color: {t.accent};
                    color: {t.accent_fg};
                    border-color: {t.accent};
                }}
            """)
            btn.clicked.connect(lambda checked, tg=tag: self._on_item_tag_clicked(tg, checked))
            self.item_tag_bar_layout.addWidget(btn)

        self.item_tag_bar_layout.addStretch()

    def _on_item_tag_clicked(self, tag, checked):
        if checked:
            self._active_item_tag = tag
        else:
            self._active_item_tag = None

        for i in range(self.item_tag_bar_layout.count()):
            w = self.item_tag_bar_layout.itemAt(i).widget()
            if w and isinstance(w, QPushButton) and w.text() != tag:
                w.setChecked(False)

        self._filter_item_rows()

    def _add_extra_item(self, item_name, units):
        # If it's a long-term item, mark as needed since user explicitly added it
        item_obj = Item()
        if item_name in item_obj.get_long_term_items():
            self.lt_have[item_name] = False

        for entry in self.extra_items:
            if entry["item_name"] == item_name:
                entry["units"] += units
                self._refresh_cart()
                return
        self.extra_items.append({"item_name": item_name, "units": units})
        self._refresh_cart()

    # ── cart management ────────────────────────────────────────── #

    def _refresh_recipe_metadata(self, recipe_name):
        """Refresh Woolworths data for every ingredient in a recipe without blocking the UI."""
        doc = Recipe().get_recipe_details(recipe_name)
        if not doc:
            return
        names = [ing.get("item_name") for ing in doc.get("ingredients", []) if ing.get("item_name")]
        run_refresh(names, on_done=self.state.items_updated, parent=self)

    def _add_recipe_to_cart(self, recipe_name, multiplier):
        self._refresh_recipe_metadata(recipe_name)
        for entry in self.recipe_entries:
            if entry["recipe_name"] == recipe_name:
                entry["multiplier"] += multiplier
                self._refresh_cart()
                return
        self.recipe_entries.append({
            "recipe_name": recipe_name,
            "multiplier": multiplier,
        })
        self._refresh_cart()

    def _remove_from_cart(self, recipe_name):
        for i, entry in enumerate(self.recipe_entries):
            if entry["recipe_name"] == recipe_name:
                self.recipe_entries.pop(i)
                break
        self._refresh_cart()

    def _remove_extra_item(self, item_name):
        for i, entry in enumerate(self.extra_items):
            if entry["item_name"] == item_name:
                self.extra_items.pop(i)
                break
        self._refresh_cart()

    def _refresh_cart(self):
        while self.cart_layout.count():
            child = self.cart_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        has_anything = self.recipe_entries or self.extra_items
        t = theme.theme()

        if not has_anything:
            self.empty_cart_label = QLabel("Add recipes or items to get started")
            self.empty_cart_label.setProperty("role", "faint")
            self.cart_layout.addWidget(self.empty_cart_label)
            self.save_button.setEnabled(False)
        else:
            if self.recipe_entries:
                recipe_header = QLabel("Recipes")
                recipe_header.setStyleSheet(
                    f"color: {t.text_dim}; font-size: 11px; font-weight: bold; padding: 2px 0;"
                )
                self.cart_layout.addWidget(recipe_header)
                for entry in self.recipe_entries:
                    card = CartEntry(
                        entry["recipe_name"],
                        entry["multiplier"],
                        self._remove_from_cart,
                    )
                    self.cart_layout.addWidget(card)

            if self.extra_items:
                item_header = QLabel("Items")
                item_header.setStyleSheet(
                    f"color: {t.text_dim}; font-size: 11px; font-weight: bold; padding: 2px 0;"
                )
                self.cart_layout.addWidget(item_header)
                for entry in self.extra_items:
                    card = ExtraItemEntry(
                        entry["item_name"],
                        entry["units"],
                        self._remove_extra_item,
                    )
                    self.cart_layout.addWidget(card)

            self.save_button.setEnabled(True)

        self._auto_render()
        self._save_draft()

    # ── draft persistence ─────────────────────────────────────── #

    @property
    def _draft_path(self):
        return app_settings.data_dir() / "shopping_draft.json"

    def _save_draft(self):
        if not self.recipe_entries and not self.extra_items:
            self._clear_draft()
            return
        draft = {
            "recipe_entries": self.recipe_entries,
            "extra_items": self.extra_items,
            "lt_have": self.lt_have,
            "name": self.name_input.text(),
        }
        self._draft_path.parent.mkdir(parents=True, exist_ok=True)
        self._draft_path.write_text(json.dumps(draft), encoding="utf-8")

    def _load_draft(self):
        if not self._draft_path.exists():
            return
        try:
            draft = json.loads(self._draft_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return
        self.recipe_entries = draft.get("recipe_entries", [])
        self.extra_items = draft.get("extra_items", [])
        self.lt_have = draft.get("lt_have", {})
        self.name_input.setText(draft.get("name", ""))
        if self.recipe_entries or self.extra_items:
            self._refresh_cart()

    def _clear_draft(self):
        if self._draft_path.exists():
            self._draft_path.unlink()

    # ── auto-render ───────────────────────────────────────────── #

    def _auto_render(self):
        """Dynamically compute and render the shopping list."""
        while self.items_scroll_layout.count():
            child = self.items_scroll_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        has_anything = self.recipe_entries or self.extra_items

        if not has_anything:
            self.preview_items = []
            self.lt_items = []
            self.lt_have = {}
            self.count_label.setText("")
            self.total_label.setText("")
            self.serves_label.setText("")
            self.export_button.setEnabled(False)
            self.links_button.setEnabled(False)
            self.items_scroll_layout.addStretch()
            self._render_lt_section()
            return

        # compute total servings (recipes only)
        recipe_obj = Recipe()
        total_servings = 0
        for entry in self.recipe_entries:
            doc = recipe_obj.get_recipe_details(entry["recipe_name"])
            base = doc.get("servings", 1) if doc else 1
            total_servings += base * entry.get("multiplier", 1)
        if total_servings > 0:
            self.serves_label.setText(f"Serves {total_servings}  \u00b7")
        else:
            self.serves_label.setText("")

        sl = ShoppingList()
        # always exclude long-term from the base list
        self.preview_items = sl.compute_items(self.recipe_entries, True, self.extra_items)

        # compute long-term items needed and build the checklist
        self.lt_items = sl.compute_long_term_items(self.recipe_entries, self.extra_items)

        # prune lt_have to only include items in self.lt_items
        lt_names = {item["item_name"] for item in self.lt_items}
        self.lt_have = {k: v for k, v in self.lt_have.items() if k in lt_names}

        self._render_lt_section()

        # merge long-term items the user doesn't have into the buy list
        for lt_item in self.lt_items:
            name = lt_item["item_name"]
            if not self.lt_have.get(name, True):  # default = have it
                self.preview_items.append(lt_item)

        self._render_preview()
        self.export_button.setEnabled(True)
        self.links_button.setEnabled(True)

    def _render_lt_section(self):
        """Rebuild the long-term items checklist."""
        while self.lt_layout.count():
            child = self.lt_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        if not self.lt_items:
            self.lt_empty_label = QLabel("No long-term items needed")
            self.lt_empty_label.setProperty("role", "faint")
            self.lt_layout.addWidget(self.lt_empty_label)
            return

        t = theme.theme()

        hint = QLabel("Uncheck items you need to buy")
        hint.setStyleSheet(f"color: {t.text_faint}; font-size: 11px; padding-bottom: 2px;")
        self.lt_layout.addWidget(hint)

        for lt_item in self.lt_items:
            name = lt_item["item_name"]
            have = self.lt_have.get(name, True)

            row = QWidget()
            row.setObjectName("lt_check_row")
            row.setFixedHeight(34)
            row.setStyleSheet(f"""
                QWidget#lt_check_row {{
                    background-color: {t.surface};
                    border-radius: 6px;
                    border: 1px solid {t.border};
                }}
            """)
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(8, 2, 8, 2)
            row_layout.setSpacing(6)

            cb = QCheckBox()
            cb.setChecked(have)
            cb.setToolTip("I have this")
            cb.setStyleSheet(theme.checkbox_css())
            cb.stateChanged.connect(
                lambda state, n=name: self._on_lt_toggled(n, bool(state))
            )
            row_layout.addWidget(cb)

            name_label = QLabel(name)
            style = f"color: {t.text_faint}; text-decoration: line-through;" if have else f"color: {t.text};"
            name_label.setStyleSheet(f"{style} font-size: 12px;")
            row_layout.addWidget(name_label, 1)

            # quantity info
            units = lt_item.get("units_needed", 1)
            if units > 1:
                qty_label = QLabel(f"x{units}")
                qty_label.setStyleSheet(f"color: {t.text}; font-size: 12px; font-weight: bold;")
                row_layout.addWidget(qty_label)

            amount = lt_item.get("amount")
            amount_unit = lt_item.get("amount_unit", "")
            if amount and amount_unit and amount_unit != "ea":
                amt = int(amount) if amount == int(amount) else amount
                amt_label = QLabel(f"{amt}{amount_unit}")
                amt_label.setStyleSheet(f"color: {t.text_dim}; font-size: 11px;")
                row_layout.addWidget(amt_label)

            price = lt_item.get("price")
            if price:
                price_label = QLabel(f"${price}")
                price_label.setStyleSheet(f"color: {t.accent}; font-size: 12px;")
                row_layout.addWidget(price_label)

            status_label = QLabel("have" if have else "need")
            status_label.setStyleSheet(
                f"color: {t.text_faint}; font-size: 10px; font-style: italic;"
                if have else
                f"color: {t.danger}; font-size: 10px; font-weight: bold;"
            )
            row_layout.addWidget(status_label)

            self.lt_layout.addWidget(row)

    def _on_lt_toggled(self, item_name, have):
        """User toggled whether they have a long-term item."""
        self.lt_have[item_name] = have
        self._auto_render()
        self._save_draft()

    def _render_preview(self):
        """Render self.preview_items into the items container."""
        grouped = {}
        for item in self.preview_items:
            tag = item.get("tags", ["Other"])[0] if item.get("tags") else "Other"
            grouped.setdefault(tag, []).append(item)

        lt_names = {it["item_name"] for it in self.lt_items}
        total = 0.0
        lt_in_list = 0.0
        count = len(self.preview_items)
        t = theme.theme()

        for i, tag in enumerate(sorted(grouped.keys())):
            if i > 0:
                spacer = QWidget()
                spacer.setFixedHeight(8)
                spacer.setStyleSheet("background: transparent;")
                self.items_scroll_layout.addWidget(spacer)

            tag_label = QLabel(tag)
            tag_label.setStyleSheet(
                f"color: {t.text_dim}; font-size: 12px; font-weight: bold; "
                f"padding: 4px 0px 2px 2px;"
            )
            self.items_scroll_layout.addWidget(tag_label)

            for item in grouped[tag]:
                widget = ShoppingItem(item, on_toggle=self._on_item_toggled)
                self.items_scroll_layout.addWidget(widget)
                if item.get("price"):
                    if item["item_name"] in lt_names:
                        lt_in_list += item["price"]
                    else:
                        total += item["price"]

        # long-term items NOT in the buy list (user already has them)
        lt_not_in_list = 0.0
        for lt_item in self.lt_items:
            if lt_item.get("price") and lt_item["item_name"] not in {
                it["item_name"] for it in self.preview_items
            }:
                lt_not_in_list += lt_item["price"]

        self.items_scroll_layout.addStretch()

        all_lt = lt_in_list + lt_not_in_list
        if all_lt > 0 and round(all_lt, 2) != 0:
            label = f"  <span style='color:{t.text_dim};font-size:11px;'>(${round(total + all_lt, 2)} w/LT)</span>&nbsp;&nbsp;&nbsp;&nbsp;Est. Total: ${round(total + lt_in_list, 2)}"
        else:
            label = f"  Est. Total: ${round(total + lt_in_list, 2)}"
        self.total_label.setText(label)
        self.count_label.setText(f"{count} items")

    def _on_save(self):
        """Save the current list with a name."""
        if not self.recipe_entries and not self.extra_items:
            return

        name = self.name_input.text().strip()
        # Determine which long-term items to exclude (the ones user has)
        lt_missing = [n for n, have in self.lt_have.items() if not have]
        self.current_list_id = ShoppingList().generate(
            self.recipe_entries, True, name, self.extra_items,
            lt_missing=lt_missing
        )
        self.name_input.clear()
        self.state.new_shopping_list.emit()
        self._clear_draft()

    def _on_item_toggled(self, item_name: str, purchased: bool):
        for item in self.preview_items:
            if item["item_name"] == item_name:
                item["purchased"] = purchased
                break

    # ── saved lists ────────────────────────────────────────────── #

    def _show_saved_lists(self):
        self._refresh_saved_list()
        self.left_stack.setCurrentIndex(1)

    def _show_recipes(self):
        self.left_stack.setCurrentIndex(0)

    def _refresh_saved_list(self):
        while self.saved_scroll_layout.count():
            child = self.saved_scroll_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        saved = ShoppingList().get_all_lists()

        if not saved:
            empty = QLabel("No saved lists yet")
            empty.setProperty("role", "faint")
            self.saved_scroll_layout.addWidget(empty)
        else:
            for name, lid, date in saved:
                card = SavedListCard(name, lid, date, self._load_saved, self._delete_saved)
                self.saved_scroll_layout.addWidget(card)

        self.saved_scroll_layout.addStretch()

    def _load_saved(self, list_id):
        self.current_list_id = list_id
        list_data = ShoppingList().get_list(list_id)
        if not list_data:
            return

        # restore cart entries
        self.recipe_entries = list_data.get("recipe_entries", [])
        self.extra_items = list_data.get("extra_items", [])
        self.name_input.setText(list_data.get("name", ""))

        # restore long-term have/need state
        lt_missing = list_data.get("lt_missing", [])
        self.lt_have = {}
        for name in lt_missing:
            self.lt_have[name] = False

        self._refresh_cart()
        self._show_recipes()

    def _delete_saved(self, list_id):
        ShoppingList().delete_list(list_id)
        self._refresh_saved_list()

    # ── export ─────────────────────────────────────────────────── #

    def _on_export(self):
        if not self.preview_items:
            return

        name = self.name_input.text().strip() or "Shopping List"
        lines = [f"Shopping List — {name}"]
        lines.append("=" * 40)

        grouped = {}
        for item in self.preview_items:
            tag = item.get("tags", ["Other"])[0] if item.get("tags") else "Other"
            grouped.setdefault(tag, []).append(item)

        total = 0.0
        for tag in sorted(grouped.keys()):
            lines.append(f"\n[{tag}]")
            for item in grouped[tag]:
                check = "\u2713" if item.get("purchased") else "\u25a1"
                units = item.get("units_needed", 1)
                amount = item.get("amount")
                amount_unit = item.get("amount_unit", "")

                amount_str = ""
                if amount and amount_unit and amount_unit != "ea":
                    amt = int(amount) if amount == int(amount) else amount
                    amount_str = f" ({amt}{amount_unit})"

                qty_str = f" x{units}" if units > 1 else ""
                price_str = f"  ${item['price']}" if item.get("price") else ""
                lines.append(f"  {check} {item['item_name']}{qty_str}{amount_str}{price_str}")
                if item.get("price"):
                    total += item["price"]

        lines.append(f"\n{'=' * 40}")
        lines.append(f"Estimated Total: ${round(total, 2)}")

        clipboard = QApplication.clipboard()
        clipboard.setText("\n".join(lines))

    def _on_links(self):
        """Add all shopping list items to the Woolworths cart via the REST API."""
        if not self.preview_items:
            return

        from kai.core.woolworths_cart import get_session, check_auth, start_cart_worker
        from kai.ui.widgets.cart_confirm_dialog import CartConfirmDialog, CartProgressDialog

        # Build item list with stock codes and quantities
        item_obj = Item()
        cart_items = []
        for item in self.preview_items:
            details = item_obj.get_item_details(item["item_name"])
            stock_code = details.get("stock_code") if details else None
            cart_items.append({
                "name": item["item_name"],
                "stock_code": stock_code,
                "qty": item.get("units_needed", 1),
                "units_needed": item.get("units_needed", 1),
                "price": item.get("price"),
            })

        # Confirmation dialog
        confirm = CartConfirmDialog(cart_items, parent=self)
        if confirm.exec() != CartConfirmDialog.DialogCode.Accepted:
            return

        accepted = confirm.accepted_items
        if not accepted:
            return

        # Try to get a valid browser session
        session = get_session()
        if session is None or not check_auth(session):
            # Auth failed — fall back to opening tabs
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(
                self,
                "Not logged in",
                f"Could not find a Woolworths session in your browser.\n\n"
                f"Please log in to woolworths.co.nz in your browser, then try again.\n\n"
                f"You can change your browser in Settings.",
            )
            for item in accepted:
                webbrowser.open(
                    f"https://www.woolworths.co.nz/shop/productdetails?stockcode={item['stock_code']}"
                )
            return

        # Worker items only need name, stock_code, qty
        worker_items = [
            {"name": i["name"], "stock_code": i["stock_code"], "qty": i["qty"]}
            for i in accepted
        ]

        progress = CartProgressDialog(len(worker_items), parent=self)

        def _on_auth_failed():
            progress.close()
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(
                self,
                "Session expired",
                "Your Woolworths session has expired.\n\n"
                "Please log in to woolworths.co.nz in your browser, then try again.",
            )
            for item in accepted:
                webbrowser.open(
                    f"https://www.woolworths.co.nz/shop/productdetails?stockcode={item['stock_code']}"
                )

        start_cart_worker(
            worker_items,
            on_item_done=progress.mark_item,
            on_auth_failed=_on_auth_failed,
            on_finished=progress.on_finished,
        )
        progress.exec()
