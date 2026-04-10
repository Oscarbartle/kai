from kai.objects.recipe import Recipe
from kai.objects.item import Item
from kai.objects.shopping_list import ShoppingList
from kai.ui import theme
from kai.ui.refresh_worker import run_refresh

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QStyle, QStyleOption
)
from PySide6.QtGui import QPainter, QCursor
from PySide6.QtCore import Qt, Signal


class RecipeView(QWidget):
    """Full recipe view — ingredients left, instructions right, independently scrollable."""

    back_requested = Signal()
    data_refreshed = Signal()

    def __init__(self, recipe_name):
        super().__init__()

        doc = Recipe().get_recipe_details(recipe_name)
        if doc is None:
            return

        self.name = doc["name"]
        self.servings = doc.get("servings", 1)
        self.tags = doc.get("tags", [])
        self.ingredients = doc.get("ingredients", [])
        self.instructions = doc.get("instructions", "")

        self._build_ui()

    def paintEvent(self, event):
        opt = QStyleOption()
        opt.initFrom(self)
        p = QPainter(self)
        self.style().drawPrimitive(QStyle.PE_Widget, opt, p, self)

    def _build_ui(self):
        t = theme.theme()

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        # ── header row ── #
        header = QHBoxLayout()
        header.setSpacing(10)

        self.back_btn = QPushButton("\u2190  Back")
        self.back_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.back_btn.setProperty("btn", "secondary")
        self.back_btn.setFixedHeight(32)
        self.back_btn.clicked.connect(self.back_requested.emit)
        header.addWidget(self.back_btn)

        title = QLabel(self.name)
        title.setStyleSheet(f"color: {t.text}; font-size: 18px; font-weight: bold;")
        header.addWidget(title)
        header.addStretch()

        meta_parts = []
        if self.servings:
            meta_parts.append(f"Serves {self.servings}")
        if self.tags:
            meta_parts.append(", ".join(self.tags))
        if meta_parts:
            meta = QLabel("\u2022  ".join(meta_parts))
            meta.setStyleSheet(f"color: {t.text_dim}; font-size: 12px;")
            meta.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            header.addWidget(meta)

        root.addLayout(header)

        # ── cost bar ── #
        cost, cost_full, cost_nominal = self._calculate_cost()
        if cost > 0:
            cost_text = f"Estimated cost: ${cost}"
            if cost_full != cost:
                cost_text += f"  <span style='color:{t.text_dim};'>(${cost_full} w/LT)</span>"
            if cost_nominal > 0:
                cost_text += f"  <span style='color:{t.text_dim};'>+${cost_nominal} nom</span>"
            cost_label = QLabel(cost_text)
            cost_label.setStyleSheet(f"color: {t.accent}; font-size: 13px; font-weight: bold;")
            root.addWidget(cost_label)

        # ── body: ingredients | instructions ── #
        body = QHBoxLayout()
        body.setSpacing(12)

        # ── left: ingredients ── #
        ing_panel = QVBoxLayout()
        ing_panel.setSpacing(8)

        ing_heading = QLabel("Ingredients")
        ing_heading.setProperty("role", "heading")
        ing_panel.addWidget(ing_heading)

        ing_scroll = QScrollArea()
        ing_scroll.setWidgetResizable(True)

        ing_content = QWidget()
        ing_content.setStyleSheet("background: transparent;")
        ing_list = QVBoxLayout(ing_content)
        ing_list.setContentsMargins(4, 4, 4, 4)
        ing_list.setSpacing(2)

        item_obj = Item()
        for ing in self.ingredients:
            name = ing.get("item_name", "?")
            amount = ing.get("amount", 1) or 1
            unit = ing.get("unit", "ea")

            # format line
            parts = []
            if ing.get("nominal"):
                parts.append("<i>~</i>")
            elif unit != "ea" or amount != 1:
                amt = int(amount) if amount == int(amount) else amount
                parts.append(f"<b>{amt}{unit}</b>")
            parts.append(name)

            # price & special detection
            doc = item_obj.get_item_details(name)
            price = item_obj.get_item_price(name)
            is_on_special = False
            if doc and doc.get("online_data"):
                sp = doc["online_data"].get("Standard Pricing", {})
                cur = sp.get("Current Price") or 0
                orig = sp.get("Original Price") or 0
                if cur and orig and cur < orig:
                    is_on_special = True

            price_str = f"  <span style='color:{t.text_faint};'>— ${price}</span>" if price else ""
            special_badge = f"  <span style='color:{t.success}; font-size:11px; font-weight:bold;'>SALE</span>" if is_on_special else ""
            is_long_term = doc.get("is_long_term", False) if doc else False
            lt_badge = f"  <span style='color:{t.text_dim}; font-size:10px;'>LT</span>" if is_long_term else ""

            bullet_color = t.success if is_on_special else (t.text_dim if is_long_term else t.accent)

            row_widget = QWidget()
            row_widget.setStyleSheet("background: transparent;")
            row_layout = QHBoxLayout(row_widget)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(4)

            row_label = QLabel(f"<span style='color:{bullet_color};'>\u2022</span>  {' '.join(parts)}{price_str}{special_badge}{lt_badge}")
            row_label.setStyleSheet(f"color: {t.text}; font-size: 13px; padding: 6px 4px;")
            row_label.setWordWrap(True)
            row_layout.addWidget(row_label, 1)

            refresh_btn = QPushButton("\u21bb")
            refresh_btn.setFixedSize(22, 22)
            refresh_btn.setToolTip(f"Refresh {name}")
            refresh_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            refresh_btn.setStyleSheet(theme.icon_btn_css())
            refresh_btn.clicked.connect(lambda checked, n=name: self._refresh_item(n))
            row_layout.addWidget(refresh_btn)

            ing_list.addWidget(row_widget)

        ing_list.addStretch()
        ing_scroll.setWidget(ing_content)
        ing_panel.addWidget(ing_scroll, 1)

        # wrap in a card
        ing_card = QWidget()
        ing_card.setObjectName("ing_card")
        ing_card.setStyleSheet(theme.inline_card_css("ing_card"))
        ing_card_layout = QVBoxLayout(ing_card)
        ing_card_layout.setContentsMargins(12, 12, 12, 12)
        ing_card_layout.setSpacing(0)
        # move widgets into the card
        ing_heading.setParent(ing_card)
        ing_scroll.setParent(ing_card)
        ing_card_layout.addWidget(ing_heading)
        ing_card_layout.addWidget(ing_scroll, 1)

        # ── right: instructions ── #
        inst_card = QWidget()
        inst_card.setObjectName("inst_card")
        inst_card.setStyleSheet(theme.inline_card_css("inst_card"))
        inst_card_layout = QVBoxLayout(inst_card)
        inst_card_layout.setContentsMargins(12, 12, 12, 12)
        inst_card_layout.setSpacing(8)

        inst_heading = QLabel("Instructions")
        inst_heading.setProperty("role", "heading")
        inst_card_layout.addWidget(inst_heading)

        inst_scroll = QScrollArea()
        inst_scroll.setWidgetResizable(True)

        inst_content = QWidget()
        inst_content.setStyleSheet("background: transparent;")
        inst_layout = QVBoxLayout(inst_content)
        inst_layout.setContentsMargins(4, 4, 4, 4)
        inst_layout.setSpacing(4)

        if self.instructions.strip():
            lines = self.instructions.strip().split("\n")
            step = 1
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                step_label = QLabel(
                    f"<span style='color:{t.accent}; font-weight:bold;'>{step}.</span>  {line}"
                )
                step_label.setStyleSheet(f"color: {t.text}; font-size: 13px; padding: 6px 4px;")
                step_label.setWordWrap(True)
                inst_layout.addWidget(step_label)
                step += 1
        else:
            empty = QLabel("No instructions added yet.")
            empty.setProperty("role", "faint")
            inst_layout.addWidget(empty)

        inst_layout.addStretch()
        inst_scroll.setWidget(inst_content)
        inst_card_layout.addWidget(inst_scroll, 1)

        body.addWidget(ing_card, 2)
        body.addWidget(inst_card, 3)

        root.addLayout(body, 1)

    def _calculate_cost(self):
        sl = ShoppingList()
        entries = [{"recipe_name": self.name, "multiplier": 1}]
        items = sl.compute_items(entries, True)
        lt_items = sl.compute_long_term_items(entries)
        nominal_items = sl.compute_nominal_items(entries)
        total = sum(it["price"] for it in items if it.get("price"))
        lt_total = sum(it["price"] for it in lt_items if it.get("price"))
        nominal_total = sum(it["price"] for it in nominal_items if it.get("price"))
        return round(total, 2), round(total + lt_total, 2), round(nominal_total, 2)

    def _refresh_item(self, item_name: str):
        run_refresh([item_name], on_done=self.data_refreshed.emit, parent=self)
