from kai.objects.recipe import Recipe
from kai.objects.item import Item
from kai.objects.shopping_list import ShoppingList
from kai.utils.format_date import format_date
from kai.ui import theme
from kai.ui.refresh_worker import run_refresh

from datetime import datetime, timedelta
from PySide6.QtWidgets import (
    QLabel, QWidget, QGridLayout, QStyle, QStyleOption,
    QHBoxLayout, QPushButton, QMessageBox, QMenu,
    QDialog, QVBoxLayout
)
from PySide6.QtGui import QPainter, QCursor, QAction
from PySide6.QtCore import Qt, Signal

# Module-level caches — busted whenever items or recipes change.
_cost_cache: dict[str, tuple] = {}
_analysis_cache: dict[str, tuple] = {}


def invalidate_recipe_card_cache():
    _cost_cache.clear()
    _analysis_cache.clear()

class RecipeDetails(QWidget):
    recipe_clicked = Signal(str)

    def __init__(self, recipe_name, state=None):
        super().__init__()

        self.state = state
        doc = Recipe().get_recipe_details(recipe_name)

        if doc is None:
            print(f"Recipe {recipe_name} not found")
            return

        self.name = doc["name"]
        self.servings = doc.get("servings", 1)
        self.tags = doc.get("tags", [])
        self.tags.sort()
        self.ingredients = doc.get("ingredients", [])
        self.instructions = doc.get("instructions", "")
        self.is_favourite = doc.get("is_favourite", False)
        self.date_added = doc.get("date_added", "")

        self.estimated_cost, self.estimated_cost_full, self.estimated_cost_nominal = self._calculate_cost()
        self.savings_regular, self.savings_lt, self.specials_count, self.is_stale, self.stale_count = self._analyse_ingredients()
        self.total_savings = self.savings_regular + self.savings_lt

        self.setObjectName("recipe_card")
        self.setMinimumHeight(62)
        self.setMaximumHeight(62)

        self.set_stylesheet()
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.layouts()
        self.add_widgets()
        self.add_layouts()

    def _calculate_cost(self):
        if self.name in _cost_cache:
            return _cost_cache[self.name]
        sl = ShoppingList()
        entries = [{"recipe_name": self.name, "multiplier": 1}]
        items = sl.compute_items(entries, True)
        lt_items = sl.compute_long_term_items(entries)
        nominal_items = sl.compute_nominal_items(entries)
        total = sum(it["price"] for it in items if it.get("price"))
        lt_total = sum(it["price"] for it in lt_items if it.get("price"))
        nominal_total = sum(it["price"] for it in nominal_items if it.get("price"))
        result = round(total, 2), round(total + lt_total, 2), round(nominal_total, 2)
        _cost_cache[self.name] = result
        return result

    def _analyse_ingredients(self):
        """Check ingredient items for specials and stale data."""
        if self.name in _analysis_cache:
            return _analysis_cache[self.name]

        item_obj = Item()
        savings_regular = 0.0
        savings_lt = 0.0
        specials_count = 0
        stale_count = 0
        is_stale = False

        for ing in self.ingredients:
            name = ing.get("item_name")
            if not name:
                continue
            doc = item_obj.get_item_details(name)
            if not doc or not doc.get("online_data"):
                continue

            # check for specials
            sp = doc["online_data"].get("Standard Pricing", {})
            current = sp.get("Current Price") or 0
            original = sp.get("Original Price") or 0
            if current and original and current < original:
                specials_count += 1
                saving = original - current
                if doc.get("is_long_term", False):
                    savings_lt += saving
                else:
                    savings_regular += saving

            # check for stale data
            date_updated = doc.get("date_updated", doc.get("date_added"))
            if date_updated:
                try:
                    updated_dt = datetime.fromisoformat(date_updated)
                    if (datetime.now() - updated_dt) > timedelta(days=7):
                        stale_count += 1
                        is_stale = True
                except (ValueError, TypeError):
                    stale_count += 1
                    is_stale = True

        result = round(savings_regular, 2), round(savings_lt, 2), specials_count, is_stale, stale_count
        _analysis_cache[self.name] = result
        return result

    def set_stylesheet(self):
        t = theme.theme()
        if self.is_favourite:
            border_color = t.accent
        else:
            border_color = t.border
        self.setStyleSheet(f"""
            QWidget#recipe_card {{
                background-color: {t.card};
                border-radius: 8px;
                border: 2px solid {border_color};
            }}
        """)

    def paintEvent(self, event):
        opt = QStyleOption()
        opt.initFrom(self)
        p = QPainter(self)
        self.style().drawPrimitive(QStyle.PE_Widget, opt, p, self)

    def layouts(self):
        self.grid_layout = QGridLayout()
        self.grid_layout.setContentsMargins(10, 6, 10, 6)
        self.grid_layout.setSpacing(5)
        self.setLayout(self.grid_layout)

    def add_widgets(self):
        t = theme.theme()

        self.name_label = QLabel(f"<b>{self.name}</b>")
        self.name_label.setStyleSheet(f"color: {t.text}; font-size: 13px;")

        self.tags_label = QLabel(f"<i>{', '.join(self.tags)}</i>")
        self.tags_label.setStyleSheet(f"color: {t.text_faint}; padding-left: 4px;")

        self.servings_label = QLabel(f"Serves {self.servings}")
        self.servings_label.setStyleSheet(f"color: {t.text_dim}; font-size: 12px;")

        ing_count = len(self.ingredients)
        self.ing_count_label = QLabel(f"{ing_count} ingredients")
        self.ing_count_label.setStyleSheet(f"color: {t.text_faint}; font-size: 11px;")

        lines = []
        for ing in self.ingredients:
            text = ing.get("item_name", "?")
            if ing.get("nominal"):
                text = f"~  {text}"
            else:
                amount = ing.get("amount", 1) or 1
                unit = ing.get("unit", "ea")
                if unit != "ea" or amount != 1:
                    amt = int(amount) if amount == int(amount) else amount
                    text = f"{amt}{unit}  {text}"
            lines.append(f"\u2022 {text}")
        self.ing_count_label.setToolTip("\n".join(lines) if lines else "No ingredients")

        # sale savings labels (green for regular, orange for LT)
        self.savings_label = None
        if self.savings_regular > 0:
            self.savings_label = QLabel(f"▼ ${self.savings_regular:.2f} off")
            self.savings_label.setStyleSheet(f"color: {t.success}; font-size: 11px; font-weight: bold;")
            self.savings_label.setToolTip("Savings from items on sale")

        # stale data warning
        if self.is_stale:
            self.stale_label = QLabel(f"⚠ {self.stale_count} stale")
            self.stale_label.setStyleSheet(f"color: {t.danger}; font-size: 10px;")
            self.stale_label.setToolTip(
                f"{self.stale_count} ingredient{'s' if self.stale_count != 1 else ''} "
                f"{'have' if self.stale_count != 1 else 'has'} data over a week old"
            )
        else:
            self.stale_label = None

        if self.estimated_cost > 0:
            cost_text = f"${self.estimated_cost}"
            tooltip_parts = []
            if self.estimated_cost_full != self.estimated_cost:
                tooltip_parts.append(f"${self.estimated_cost_full} with long-term items")
            if self.estimated_cost_nominal > 0:
                tooltip_parts.append(f"+${self.estimated_cost_nominal} nominal")
            cost_tooltip = "\n".join(tooltip_parts) if tooltip_parts else ""
        else:
            cost_text = "N/A"
            cost_tooltip = ""
        self.cost_label = QLabel(f"<b>{cost_text}</b>")
        self.cost_label.setStyleSheet(f"color: {t.accent}; font-size: 14px;")
        if cost_tooltip:
            self.cost_label.setToolTip(cost_tooltip)

        self.date_label = QLabel(f"{format_date(self.date_added)}" if self.date_added else "")
        self.date_label.setStyleSheet(f"color: {t.text_faint}; font-size: 11px;")
        self.date_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        fav_color = t.accent if self.is_favourite else t.text_faint
        self.fav_button = QPushButton("\u2605")
        self.fav_button.setFixedSize(22, 22)
        self.fav_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.fav_button.setToolTip("Favourite recipe")
        self.fav_button.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {fav_color};
                border: none; font-size: 14px;
            }}
            QPushButton:hover {{ color: {t.accent}; }}
        """)
        self.fav_button.clicked.connect(self._on_fav_toggled)

        self.refresh_button = QPushButton("\u21bb")
        self.refresh_button.setFixedSize(22, 22)
        self.refresh_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.refresh_button.setToolTip("Refresh ingredient prices")
        self.refresh_button.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {t.text_faint};
                border: none; font-size: 14px; font-weight: bold;
                border-radius: 4px;
            }}
            QPushButton:hover {{ background: {t.accent}22; color: {t.accent}; }}
        """)
        self.refresh_button.clicked.connect(self._on_refresh)

        self.delete_button = QPushButton("\u2715")
        self.delete_button.setFixedSize(22, 22)
        self.delete_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.delete_button.setToolTip("Delete recipe")
        self.delete_button.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {t.text_faint};
                border: none; font-size: 14px; font-weight: bold;
            }}
            QPushButton:hover {{ color: {t.danger}; background: {t.danger}22; border-radius: 4px; }}
        """)
        self.delete_button.clicked.connect(self._on_delete)

    def add_layouts(self):
        # Row 0: name | tags (stretch) | ★ | ↻ | date | ✕
        self.grid_layout.addWidget(self.name_label, 0, 0)
        self.grid_layout.addWidget(self.tags_label, 0, 1)
        self.grid_layout.setColumnStretch(1, 1)

        right_row0 = QHBoxLayout()
        right_row0.setContentsMargins(0, 0, 0, 0)
        right_row0.setSpacing(6)
        right_row0.addWidget(self.refresh_button)
        right_row0.addWidget(self.fav_button)
        right_row0.addWidget(self.date_label)
        right_row0.addSpacing(8)
        right_row0.addWidget(self.delete_button)
        self.grid_layout.addLayout(right_row0, 0, 2)

        # Row 1: servings | ing_count | sale/stale indicators | cost
        self.grid_layout.addWidget(self.servings_label, 1, 0)
        self.grid_layout.addWidget(self.ing_count_label, 1, 1)

        right_row1 = QHBoxLayout()
        right_row1.setContentsMargins(0, 0, 0, 0)
        right_row1.setSpacing(12)
        right_row1.addStretch()
        if self.stale_label:
            right_row1.addWidget(self.stale_label)
        if self.savings_label:
            right_row1.addWidget(self.savings_label)
        right_row1.addWidget(self.cost_label)
        self.grid_layout.addLayout(right_row1, 1, 2)

    def _on_fav_toggled(self):
        self.is_favourite = not self.is_favourite
        Recipe().update(self.name, "is_favourite", self.is_favourite)
        if self.state:
            self.state.recipes_updated()

    def _on_refresh(self):
        """Refresh Woolworths data for every ingredient in this recipe."""
        names = [ing.get("item_name") for ing in self.ingredients if ing.get("item_name")]
        callbacks = []
        if self.state:
            callbacks = [self.state.items_updated, self.state.recipes_updated]
        run_refresh(names, on_done=callbacks, parent=self)

    def _on_delete(self):
        reply = QMessageBox.question(
            self, "Delete Recipe",
            f"Delete \u201c{self.name}\u201d?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        Recipe().delete(self.name)
        if self.state:
            self.state.recipes_updated()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.recipe_clicked.emit(self.name)
        super().mousePressEvent(event)

    def contextMenuEvent(self, event):
        p = theme._active
        menu = QMenu(self)
        menu.setStyleSheet(
            f"QMenu {{ background:{p.surface}; color:{p.text}; border:1px solid {p.border}; padding:4px; }}"
            f"QMenu::item {{ padding:6px 24px 6px 12px; border-radius:4px; }}"
            f"QMenu::item:selected {{ background:{p.accent}; color:{p.accent_fg}; }}"
        )
        edit_action = QAction("Edit Recipe", self)
        edit_action.triggered.connect(self._open_edit_dialog)
        menu.addAction(edit_action)
        menu.exec(event.globalPos())

    def _open_edit_dialog(self):
        from kai.ui.layouts.recipes_add import RecipesAdd

        dialog = QDialog(self.window())
        dialog.setWindowTitle(f"Edit — {self.name}")
        dialog.setMinimumSize(720, 520)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(0, 0, 0, 0)

        form = RecipesAdd(self.state, edit_recipe=self.name)
        layout.addWidget(form)

        dialog.exec()
