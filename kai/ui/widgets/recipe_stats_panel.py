from __future__ import annotations

from kai.objects.recipe import Recipe
from kai.objects.item import Item
from kai.core.backend import get_shopping_list
from kai.objects.order_history import OrderHistory
from kai.ui import theme
from kai.ui.tokens import SPACE_SM, SPACE_MD, SPACE_LG, RADIUS_MD, FS_BODY, FS_META, FS_TINY

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QStyle, QStyleOption, QScrollArea,
)
from PySide6.QtGui import QPainter
from PySide6.QtCore import Qt


class _InfoCard(QWidget):
    """Stat card: label + big value + optional sub-label."""

    def __init__(self, label: str, value: str, sub: str = "", color: str = None):
        super().__init__()
        t = theme.theme()
        self.setObjectName("stat_card")
        self.setStyleSheet(theme.inline_card_css("stat_card", radius=RADIUS_MD))

        lay = QVBoxLayout(self)
        lay.setContentsMargins(SPACE_MD, SPACE_SM, SPACE_MD, SPACE_SM)
        lay.setSpacing(2)

        lbl = QLabel(label)
        lbl.setStyleSheet(f"color: {t.text_dim}; font-size: {FS_META}px;")
        lay.addWidget(lbl)

        val = QLabel(value)
        val.setStyleSheet(f"color: {color or t.text}; font-size: 20px; font-weight: bold;")
        lay.addWidget(val)

        if sub:
            sub_lbl = QLabel(sub)
            sub_lbl.setStyleSheet(f"color: {t.text_faint}; font-size: {FS_TINY}px;")
            lay.addWidget(sub_lbl)

    def paintEvent(self, event):
        opt = QStyleOption()
        opt.initFrom(self)
        p = QPainter(self)
        self.style().drawPrimitive(QStyle.PE_Widget, opt, p, self)


class _IngRow(QWidget):
    def __init__(self, rank: int, name: str, price: float, is_special: bool, order_count: int = 0):
        super().__init__()
        t = theme.theme()
        self.setStyleSheet("background: transparent;")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 2, 0, 2)
        lay.setSpacing(SPACE_SM)

        rank_lbl = QLabel(f"{rank}.")
        rank_lbl.setFixedWidth(20)
        rank_lbl.setStyleSheet(f"color: {t.text_dim}; font-size: {FS_META}px;")
        lay.addWidget(rank_lbl)

        name_lbl = QLabel(name)
        name_lbl.setStyleSheet(f"color: {t.text}; font-size: {FS_BODY}px;")
        lay.addWidget(name_lbl, 1)

        if is_special:
            sale_badge = QLabel("SALE")
            sale_badge.setStyleSheet(
                f"color: {t.success}; font-size: {FS_TINY}px; font-weight: bold;"
            )
            lay.addWidget(sale_badge)

        if order_count > 0:
            orders_lbl = QLabel(f"×{order_count}")
            orders_lbl.setStyleSheet(f"color: {t.text_dim}; font-size: {FS_TINY}px;")
            lay.addWidget(orders_lbl)

        price_lbl = QLabel(f"${price:.2f}")
        price_lbl.setStyleSheet(
            f"color: {t.success if is_special else t.accent}; font-size: {FS_BODY}px; font-weight: bold;"
        )
        lay.addWidget(price_lbl)


class RecipeStatsPanel(QWidget):
    """Stats panel for a recipe — stat cards + sorted ingredient list."""

    def __init__(self, recipe_name: str):
        super().__init__()
        self._name = recipe_name
        self._build_ui()

    def paintEvent(self, event):
        opt = QStyleOption()
        opt.initFrom(self)
        p = QPainter(self)
        self.style().drawPrimitive(QStyle.PE_Widget, opt, p, self)

    def _build_ui(self):
        t = theme.theme()

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("background: transparent; border: none;")

        container = QWidget()
        container.setStyleSheet("background: transparent;")
        root = QVBoxLayout(container)
        root.setContentsMargins(0, 0, SPACE_SM, 0)
        root.setSpacing(SPACE_MD)

        # ── gather data ── #
        doc = get_recipe().get_recipe_details(self._name)
        ingredients = doc.get("ingredients", []) if doc else []
        servings = doc.get("servings", 1) if doc else 1

        item_obj = get_item()
        sl = get_shopping_list()
        entries = [{"recipe_name": self._name, "multiplier": 1}]
        try:
            items = sl.compute_items(entries, exclude_long_term=True)
            lt_items = sl.compute_long_term_items(entries)
            nominal_items = sl.compute_nominal_items(entries)
        except NotImplementedError:
            items = lt_items = nominal_items = []

        total = sum(it["price"] for it in items if it.get("price"))
        lt_total = sum(it["price"] for it in lt_items if it.get("price"))
        nom_total = sum(it["price"] for it in nominal_items if it.get("price"))

        on_special = [it for it in items if self._is_on_special(it["item_name"], item_obj)]
        savings = sum(
            self._special_savings(it["item_name"], item_obj) * it.get("units_needed", 1)
            for it in on_special
        )
        missing_price = [it for it in items if not it.get("price")]

        # find most expensive ingredient by unit price
        priced = [(it["item_name"], it["price"]) for it in items if it.get("price")]
        priced.sort(key=lambda x: x[1], reverse=True)
        priciest = priced[0] if priced else None

        # ── stat cards row 1 ── #
        row1 = QHBoxLayout()
        row1.setSpacing(SPACE_SM)
        row1.addWidget(_InfoCard(
            "Recipe Cost",
            f"${total:.2f}",
            sub=f"${total/servings:.2f} per serving" if servings else "",
            color=t.accent,
        ))
        row1.addWidget(_InfoCard(
            "With Long-term",
            f"${total + lt_total:.2f}",
            sub=f"+${lt_total:.2f} LT items" if lt_total else "No LT items",
        ))
        row1.addWidget(_InfoCard(
            "Ingredients",
            str(len(ingredients)),
            sub=f"{len(missing_price)} without price" if missing_price else "All priced",
        ))
        row1.addWidget(_InfoCard(
            "Servings",
            str(servings),
            sub=f"${total/servings:.2f} ea" if servings and total else "",
        ))
        root.addLayout(row1)

        # ── stat cards row 2 ── #
        row2 = QHBoxLayout()
        row2.setSpacing(SPACE_SM)
        row2.addWidget(_InfoCard(
            "On Special",
            str(len(on_special)),
            sub=f"Saving ${savings:.2f}" if savings else "No active specials",
            color=t.success if on_special else None,
        ))
        row2.addWidget(_InfoCard(
            "Nominal Items",
            str(len(nominal_items)),
            sub=f"${nom_total:.2f} if purchased" if nom_total else "Things you likely have",
        ))
        if priciest:
            row2.addWidget(_InfoCard(
                "Priciest Ingredient",
                f"${priciest[1]:.2f}",
                sub=priciest[0],
                color=t.accent,
            ))
        else:
            row2.addWidget(_InfoCard("Priciest Ingredient", "—"))
        row2.addWidget(_InfoCard(
            "Long-term Items",
            str(len(lt_items)),
            sub=f"${lt_total:.2f} total" if lt_total else "",
        ))
        root.addLayout(row2)

        # ── order history row ── #
        oh = OrderHistory()
        ing_names = [it["item_name"] for it in items]
        order_entries = [(n, oh.get(n).get("count", 0)) for n in ing_names]
        order_entries.sort(key=lambda x: x[1], reverse=True)
        top_ordered = order_entries[0] if order_entries and order_entries[0][1] > 0 else None
        never_ordered_count = sum(1 for _, c in order_entries if c == 0)

        row3 = QHBoxLayout()
        row3.setSpacing(SPACE_SM)
        row3.addWidget(_InfoCard(
            "Most Ordered Ingredient",
            top_ordered[0] if top_ordered else "None yet",
            sub=f"{top_ordered[1]} orders" if top_ordered else "No orders recorded",
            color=t.accent if top_ordered else None,
        ))
        row3.addWidget(_InfoCard(
            "Never Ordered",
            str(never_ordered_count),
            sub="ingredient(s) with no orders" if never_ordered_count else "All ingredients ordered",
        ))
        row3.addStretch()
        root.addLayout(row3)

        # ── sorted ingredient list ── #
        if priced:
            heading = QLabel("Ingredients by Cost")
            heading.setProperty("role", "heading")
            root.addWidget(heading)

            all_ing_prices = []
            for it in items:
                if it.get("price"):
                    all_ing_prices.append((it["item_name"], it["price"]))
            all_ing_prices.sort(key=lambda x: x[1], reverse=True)

            special_names = {it["item_name"] for it in on_special}
            order_counts = {n: c for n, c in order_entries}
            for i, (name, price) in enumerate(all_ing_prices, 1):
                root.addWidget(_IngRow(i, name, price, name in special_names, order_counts.get(name, 0)))

        root.addStretch()
        scroll.setWidget(container)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

    @staticmethod
    def _is_on_special(name: str, item_obj: Item) -> bool:
        doc = item_obj.get_item_details(name)
        if not doc or not doc.get("online_data"):
            return False
        sp = doc["online_data"].get("Standard Pricing", {})
        cur = sp.get("Current Price") or 0
        orig = sp.get("Original Price") or 0
        return bool(cur and orig and float(cur) < float(orig))

    @staticmethod
    def _special_savings(name: str, item_obj: Item) -> float:
        doc = item_obj.get_item_details(name)
        if not doc or not doc.get("online_data"):
            return 0.0
        sp = doc["online_data"].get("Standard Pricing", {})
        cur = sp.get("Current Price") or 0
        orig = sp.get("Original Price") or 0
        return max(0.0, float(orig) - float(cur))
