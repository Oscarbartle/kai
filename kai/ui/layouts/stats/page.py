from __future__ import annotations

from datetime import datetime

from kai.objects.item import Item
from kai.objects.recipe import Recipe
from kai.objects.price_history import PriceHistory
from kai.objects.shopping_list import ShoppingList
from kai.core.backend import get_item, get_recipe, get_shopping_list
from kai.core import settings as app_settings
from kai.ui import theme
from kai.ui.tokens import (
    SPACE_SM, SPACE_MD, SPACE_LG,
    RADIUS_MD, RADIUS_SM,
    FS_BODY, FS_META, FS_TINY, FS_HEADING,
    FW_BOLD,
)

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea,
    QStyle, QStyleOption, QGridLayout, QPushButton, QFrame,
)
from PySide6.QtGui import QPainter, QCursor
from PySide6.QtCore import Qt, Signal


# ── reusable primitives ──────────────────────────────────────────── #

class _Card(QWidget):
    def paintEvent(self, event):
        opt = QStyleOption()
        opt.initFrom(self)
        p = QPainter(self)
        self.style().drawPrimitive(QStyle.PE_Widget, opt, p, self)


def _divider():
    line = QFrame()
    line.setFrameShape(QFrame.Shape.HLine)
    t = theme.theme()
    line.setStyleSheet(f"color: {t.border}; border: none; border-top: 1px solid {t.border};")
    return line


def _section_heading(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setProperty("role", "heading")
    return lbl


class _SummaryTile(_Card):
    """Top-bar summary tile: icon + number + label."""

    def __init__(self, icon: str, value: str, label: str, color: str = None, sub: str = ""):
        super().__init__()
        t = theme.theme()
        self.setObjectName("summary_tile")
        self.setStyleSheet(theme.inline_card_css("summary_tile", radius=RADIUS_MD))

        lay = QVBoxLayout(self)
        lay.setContentsMargins(SPACE_MD, SPACE_MD, SPACE_MD, SPACE_MD)
        lay.setSpacing(2)

        top = QHBoxLayout()
        top.setSpacing(SPACE_SM)
        icon_lbl = QLabel(icon)
        icon_lbl.setStyleSheet(f"font-size: 20px;")
        top.addWidget(icon_lbl)
        top.addStretch()
        lay.addLayout(top)

        val = QLabel(value)
        val.setStyleSheet(f"color: {color or t.text}; font-size: 26px; font-weight: bold;")
        lay.addWidget(val)

        desc = QLabel(label)
        desc.setStyleSheet(f"color: {t.text_dim}; font-size: {FS_META}px;")
        lay.addWidget(desc)

        if sub:
            sub_lbl = QLabel(sub)
            sub_lbl.setStyleSheet(f"color: {t.text_faint}; font-size: {FS_TINY}px;")
            lay.addWidget(sub_lbl)


class _DealCard(_Card):
    """Card for a single hot deal."""

    def __init__(self, rank: int, name: str, current: float, original: float, tags: list):
        super().__init__()
        t = theme.theme()
        self.setObjectName("deal_card")
        self.setStyleSheet(theme.inline_card_css("deal_card", radius=RADIUS_MD))

        pct = round((original - current) / original * 100) if original else 0

        lay = QVBoxLayout(self)
        lay.setContentsMargins(SPACE_MD, SPACE_SM, SPACE_MD, SPACE_SM)
        lay.setSpacing(4)

        # rank + name
        header = QHBoxLayout()
        header.setSpacing(SPACE_SM)
        rank_lbl = QLabel(f"#{rank}")
        rank_lbl.setStyleSheet(f"color: {t.text_faint}; font-size: {FS_META}px;")
        header.addWidget(rank_lbl)
        name_lbl = QLabel(f"<b>{name}</b>")
        name_lbl.setStyleSheet(f"color: {t.text}; font-size: {FS_BODY}px;")
        header.addWidget(name_lbl, 1)
        lay.addLayout(header)

        # price row
        price_row = QHBoxLayout()
        price_row.setSpacing(SPACE_SM)
        cur_lbl = QLabel(f"<b>${current:.2f}</b>")
        cur_lbl.setStyleSheet(f"color: {t.success}; font-size: 18px;")
        price_row.addWidget(cur_lbl)
        was_lbl = QLabel(f"<s>${original:.2f}</s>")
        was_lbl.setStyleSheet(f"color: {t.text_faint}; font-size: {FS_BODY}px;")
        price_row.addWidget(was_lbl)
        price_row.addStretch()
        lay.addLayout(price_row)

        # discount badge + tags
        footer = QHBoxLayout()
        footer.setSpacing(SPACE_SM)
        disc_badge = QLabel(f"  {pct}% off  ")
        disc_badge.setStyleSheet(
            f"background: {t.success}; color: #0a2e1a; border-radius: 8px;"
            f" font-size: {FS_TINY}px; font-weight: bold; padding: 2px 0;"
        )
        footer.addWidget(disc_badge)
        savings_lbl = QLabel(f"Save ${original - current:.2f}")
        savings_lbl.setStyleSheet(f"color: {t.success}; font-size: {FS_TINY}px;")
        footer.addWidget(savings_lbl)
        footer.addStretch()
        if tags:
            tag_lbl = QLabel(tags[0])
            tag_lbl.setStyleSheet(f"color: {t.text_faint}; font-size: {FS_TINY}px;")
            footer.addWidget(tag_lbl)
        lay.addLayout(footer)


class _PriceLowCard(_Card):
    """Card for an item at its N-day or all-time low."""

    def __init__(self, name: str, current: float, low_type: str, prev_high: float | None, tags: list):
        super().__init__()
        t = theme.theme()
        self.setObjectName("low_card")
        self.setStyleSheet(theme.inline_card_css("low_card", radius=RADIUS_MD))

        lay = QVBoxLayout(self)
        lay.setContentsMargins(SPACE_MD, SPACE_SM, SPACE_MD, SPACE_SM)
        lay.setSpacing(4)

        name_lbl = QLabel(f"<b>{name}</b>")
        name_lbl.setStyleSheet(f"color: {t.text}; font-size: {FS_BODY}px;")
        lay.addWidget(name_lbl)

        price_row = QHBoxLayout()
        price_row.setSpacing(SPACE_SM)
        cur_lbl = QLabel(f"<b>${current:.2f}</b>")
        cur_lbl.setStyleSheet(f"color: {t.accent}; font-size: 18px;")
        price_row.addWidget(cur_lbl)
        if low_type == "all-time":
            badge = QLabel("  ★ all-time low  ")
            badge.setStyleSheet(
                f"background: #fef3c7; color: #92400e; border-radius: 8px;"
                f" font-size: {FS_TINY}px; font-weight: bold; padding: 2px 0;"
            )
        else:
            badge = QLabel(f"  ↓ {low_type}  ")
            badge.setStyleSheet(
                f"background: #dcfce7; color: #14532d; border-radius: 8px;"
                f" font-size: {FS_TINY}px; font-weight: bold; padding: 2px 0;"
            )
        price_row.addWidget(badge)
        price_row.addStretch()
        lay.addLayout(price_row)

        if prev_high is not None and prev_high > current:
            delta_lbl = QLabel(f"↓ from ${prev_high:.2f} high")
            delta_lbl.setStyleSheet(f"color: {t.text_faint}; font-size: {FS_TINY}px;")
            lay.addWidget(delta_lbl)


class _ChangeCard(_Card):
    """Card showing a price rise or drop."""

    def __init__(self, name: str, current: float, previous: float, tags: list):
        super().__init__()
        t = theme.theme()
        self.setObjectName("change_card")
        self.setStyleSheet(theme.inline_card_css("change_card", radius=RADIUS_MD))

        delta = current - previous
        pct = abs(delta / previous * 100) if previous else 0
        rising = delta > 0

        lay = QVBoxLayout(self)
        lay.setContentsMargins(SPACE_MD, SPACE_SM, SPACE_MD, SPACE_SM)
        lay.setSpacing(4)

        name_lbl = QLabel(f"<b>{name}</b>")
        name_lbl.setStyleSheet(f"color: {t.text}; font-size: {FS_BODY}px;")
        lay.addWidget(name_lbl)

        price_row = QHBoxLayout()
        price_row.setSpacing(SPACE_SM)
        arrow = "↑" if rising else "↓"
        color = t.danger if rising else t.success
        cur_lbl = QLabel(f"<b>{arrow} ${current:.2f}</b>")
        cur_lbl.setStyleSheet(f"color: {color}; font-size: 18px;")
        price_row.addWidget(cur_lbl)
        was_lbl = QLabel(f"was ${previous:.2f}")
        was_lbl.setStyleSheet(f"color: {t.text_faint}; font-size: {FS_META}px;")
        price_row.addWidget(was_lbl)
        price_row.addStretch()
        pct_lbl = QLabel(f"{pct:.0f}%")
        pct_lbl.setStyleSheet(f"color: {color}; font-size: {FS_META}px; font-weight: bold;")
        price_row.addWidget(pct_lbl)
        lay.addLayout(price_row)

        if tags:
            tag_lbl = QLabel(tags[0])
            tag_lbl.setStyleSheet(f"color: {t.text_faint}; font-size: {FS_TINY}px;")
            lay.addWidget(tag_lbl)


class _RecipeCard(_Card):
    """Card for a recipe insight."""

    def __init__(self, label: str, name: str, cost: float, detail: str = "",
                 savings: float = 0.0, color: str = None):
        super().__init__()
        t = theme.theme()
        self.setObjectName("recipe_insight_card")
        self.setStyleSheet(theme.inline_card_css("recipe_insight_card", radius=RADIUS_MD))

        lay = QVBoxLayout(self)
        lay.setContentsMargins(SPACE_MD, SPACE_SM, SPACE_MD, SPACE_SM)
        lay.setSpacing(4)

        cat_lbl = QLabel(label.upper())
        cat_lbl.setStyleSheet(
            f"color: {t.text_faint}; font-size: {FS_TINY}px; font-weight: bold; letter-spacing: 1px;"
        )
        lay.addWidget(cat_lbl)

        name_lbl = QLabel(f"<b>{name}</b>")
        name_lbl.setStyleSheet(f"color: {t.text}; font-size: {FS_BODY}px;")
        name_lbl.setWordWrap(True)
        lay.addWidget(name_lbl)

        price_lbl = QLabel(f"${cost:.2f}")
        price_lbl.setStyleSheet(f"color: {color or t.accent}; font-size: 20px; font-weight: bold;")
        lay.addWidget(price_lbl)

        if savings > 0:
            save_lbl = QLabel(f"Save ${savings:.2f}")
            save_lbl.setStyleSheet(
                f"color: {t.success}; font-size: {FS_META}px; font-weight: bold;"
            )
            lay.addWidget(save_lbl)

        if detail:
            det_lbl = QLabel(detail)
            det_lbl.setStyleSheet(f"color: {t.text_faint}; font-size: {FS_TINY}px;")
            lay.addWidget(det_lbl)


class _OrderCard(_Card):
    """Card showing order count for a single item."""

    def __init__(self, rank: int, name: str, count: int, last_date: str, tags: list):
        super().__init__()
        t = theme.theme()
        self.setObjectName("order_card")
        self.setStyleSheet(theme.inline_card_css("order_card", radius=RADIUS_MD))

        lay = QVBoxLayout(self)
        lay.setContentsMargins(SPACE_MD, SPACE_SM, SPACE_MD, SPACE_SM)
        lay.setSpacing(3)

        header = QHBoxLayout()
        header.setSpacing(SPACE_SM)
        rank_lbl = QLabel(f"#{rank}")
        rank_lbl.setStyleSheet(f"color: {t.text_faint}; font-size: {FS_TINY}px;")
        header.addWidget(rank_lbl)
        if tags:
            tag_lbl = QLabel(tags[0])
            tag_lbl.setStyleSheet(f"color: {t.text_faint}; font-size: {FS_TINY}px;")
            header.addWidget(tag_lbl)
        header.addStretch()
        lay.addLayout(header)

        name_lbl = QLabel(f"<b>{name}</b>")
        name_lbl.setStyleSheet(f"color: {t.text}; font-size: {FS_BODY}px;")
        name_lbl.setWordWrap(True)
        lay.addWidget(name_lbl)

        count_row = QHBoxLayout()
        count_row.setSpacing(SPACE_SM)
        count_lbl = QLabel(str(count))
        count_lbl.setStyleSheet(f"color: {t.accent}; font-size: 22px; font-weight: bold;")
        count_row.addWidget(count_lbl)
        times_lbl = QLabel("orders")
        times_lbl.setStyleSheet(f"color: {t.text_dim}; font-size: {FS_META}px; padding-top: 4px;")
        count_row.addWidget(times_lbl)
        count_row.addStretch()
        lay.addLayout(count_row)

        if last_date:
            from kai.utils.format_date import format_date
            last_lbl = QLabel(f"Last: {format_date(last_date)}")
            last_lbl.setStyleSheet(f"color: {t.text_faint}; font-size: {FS_TINY}px;")
            lay.addWidget(last_lbl)


def _grid(cards: list, cols: int = 3) -> QGridLayout:
    grid = QGridLayout()
    grid.setSpacing(SPACE_SM)
    for i, card in enumerate(cards):
        grid.addWidget(card, i // cols, i % cols)
    return grid


# ── main stats page ─────────────────────────────────────────────── #

class StatsPage(QWidget):
    """Top-level stats & insights page."""

    def __init__(self, state=None):
        super().__init__()
        self._state = state
        self._build_ui()
        if state:
            state.new_items.connect(self._rebuild)
            state.new_recipes.connect(self._rebuild)

    def paintEvent(self, event):
        opt = QStyleOption()
        opt.initFrom(self)
        p = QPainter(self)
        self.style().drawPrimitive(QStyle.PE_Widget, opt, p, self)

    def _rebuild(self):
        # replace inner widget entirely
        old = self.layout().itemAt(0).widget() if self.layout() else None
        self._build_ui()
        if old:
            old.deleteLater()

    def _build_ui(self):
        # clear existing layout if rebuilding
        if self.layout():
            while self.layout().count():
                item = self.layout().takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
            return_layout = self.layout()
        else:
            return_layout = QVBoxLayout(self)
            return_layout.setContentsMargins(0, 0, 0, 0)
            return_layout.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("background: transparent; border: none;")

        container = QWidget()
        container.setStyleSheet("background: transparent;")
        root = QVBoxLayout(container)
        root.setContentsMargins(SPACE_LG, SPACE_LG, SPACE_LG, SPACE_LG)
        root.setSpacing(SPACE_LG)

        # ── gather all data ── #
        item_obj = get_item()
        ph = PriceHistory()
        window = int(app_settings.get("price_history_window_days") or 30)

        all_docs = list(item_obj.io.all().items())  # [(id, doc)]

        on_special = []
        at_n_low = []
        at_alltime_low = []
        price_rises = []
        price_drops = []


        for item_id, doc in all_docs:
            name = doc.get("name", "")
            sp = (doc.get("online_data") or {}).get("Standard Pricing", {})
            cur = sp.get("Current Price")
            orig = sp.get("Original Price")
            tags = doc.get("tags") or []

            if cur is None:
                continue

            cur = float(cur)

            if orig is not None:
                orig = float(orig)
                if cur < orig:
                    on_special.append({
                        "name": name, "current": cur, "original": orig,
                        "tags": tags, "saving": orig - cur,
                    })

            # price history flags
            history = ph.get(item_id)
            if len(history) >= 2:
                prev = history[-2].get("current_price")
                if prev is not None:
                    prev = float(prev)
                    if cur > prev * 1.005:
                        price_rises.append({
                            "name": name, "current": cur, "previous": prev,
                            "delta": cur - prev, "tags": tags,
                        })
                    elif cur < prev * 0.995:
                        price_drops.append({
                            "name": name, "current": cur, "previous": prev,
                            "delta": prev - cur, "tags": tags,
                        })

            at_min = ph.all_time_min(item_id)
            at_max = ph.all_time_max(item_id)
            n_min = ph.min_in_window(item_id, window)

            if at_min is not None and cur <= at_min:
                at_alltime_low.append({
                    "name": name, "current": cur,
                    "high": at_max, "tags": tags, "type": "all-time",
                })
            elif n_min is not None and cur <= n_min:
                at_n_low.append({
                    "name": name, "current": cur,
                    "high": at_max, "tags": tags, "type": f"{window}d low",
                })

        on_special.sort(key=lambda x: x["saving"], reverse=True)
        price_rises.sort(key=lambda x: x["delta"], reverse=True)
        price_drops.sort(key=lambda x: x["delta"], reverse=True)

        # recipe costs
        recipe_obj = get_recipe()
        sl = get_shopping_list()
        recipe_costs = []
        for name, _ in recipe_obj.get_recipes():
            try:
                items = sl.compute_items([{"recipe_name": name, "multiplier": 1}], True)
                cost = sum(it["price"] for it in items if it.get("price"))
                if cost > 0:
                    doc = recipe_obj.get_recipe_details(name)
                    servings = (doc or {}).get("servings", 1) or 1
                    recipe_costs.append({
                        "name": name, "cost": round(cost, 2),
                        "per_serving": round(cost / servings, 2),
                        "servings": servings,
                    })
            except Exception:
                pass
        recipe_costs.sort(key=lambda x: x["cost"])

        # ── header ── #
        heading = QLabel("Insights")
        heading.setStyleSheet(f"font-size: 22px; font-weight: bold; color: {theme.theme().text};")
        root.addWidget(heading)

        # ── summary tiles ── #
        t = theme.theme()
        total_savings = sum(x["saving"] for x in on_special)
        tile_list = [
            _SummaryTile("🏷️", str(len(on_special)), "On Special Now",
                         color=t.success if on_special else None,
                         sub=f"Save ${total_savings:.2f} total" if total_savings else ""),
            _SummaryTile("📉", str(len(at_alltime_low) + len(at_n_low)),
                         "At Price Lows",
                         color=t.accent if (at_alltime_low or at_n_low) else None,
                         sub=f"{len(at_alltime_low)} all-time · {len(at_n_low)} {window}d"),
            _SummaryTile("📈", str(len(price_rises)),
                         "Prices Up",
                         color=t.danger if price_rises else None,
                         sub="since last refresh"),
            _SummaryTile("📉", str(len(price_drops)),
                         "Prices Down",
                         color=t.success if price_drops else None,
                         sub="since last refresh"),
        ]
        tiles_widget = QWidget()
        tiles_widget.setStyleSheet("background: transparent;")
        tiles_widget.setLayout(_grid(tile_list, cols=4))
        root.addWidget(tiles_widget)

        root.addWidget(_divider())

        # ── hot deals ── #
        root.addWidget(_section_heading(f"🔥  Hot Deals"))
        if on_special:
            deal_grid = _grid(
                [_DealCard(i + 1, d["name"], d["current"], d["original"], d["tags"])
                 for i, d in enumerate(on_special[:6])],
                cols=3,
            )
            deal_widget = QWidget()
            deal_widget.setStyleSheet("background: transparent;")
            deal_widget.setLayout(deal_grid)
            root.addWidget(deal_widget)
        else:
            root.addWidget(_empty("No specials active right now — check back after the next refresh."))

        root.addWidget(_divider())

        # ── order history ── #
        from kai.objects.order_history import OrderHistory
        oh = OrderHistory()
        top_orders = oh.top(6)
        all_item_names = [doc.get("name") for _, doc in all_docs if doc.get("name")]
        never = oh.never_ordered(all_item_names)

        root.addWidget(_section_heading("🛒  Most Ordered Items"))

        if any(count > 0 for _, count in top_orders):
            order_cards = []
            item_obj2 = get_item()
            for rank, (name, count) in enumerate(top_orders, 1):
                if count == 0:
                    break
                doc2 = item_obj2.get_item_details(name) or {}
                entry = oh.get(name)
                order_cards.append(_OrderCard(
                    rank, name, count,
                    last_date=entry.get("last_date", ""),
                    tags=doc2.get("tags") or [],
                ))
            if order_cards:
                ord_widget = QWidget()
                ord_widget.setStyleSheet("background: transparent;")
                ord_widget.setLayout(_grid(order_cards, cols=3))
                root.addWidget(ord_widget)

            total_orders = sum(d.get("count", 0) for d in oh.all().values())
            unique_ordered = len([d for d in oh.all().values() if d.get("count", 0) > 0])
            summary_tiles = [
                _SummaryTile("📦", str(total_orders), "Total Cart Events",
                             sub=f"across {unique_ordered} unique items"),
                _SummaryTile("🆕", str(len(never)), "Never Ordered",
                             sub="items not yet added to cart" if never else "All items ordered at least once",
                             color=t.text_dim if never else t.success),
            ]
            if top_orders and top_orders[0][1] > 0:
                summary_tiles.append(_SummaryTile(
                    "🏆", top_orders[0][0], "Most Ordered",
                    sub=f"ordered {top_orders[0][1]}× total",
                    color=t.accent,
                ))
            summ_widget = QWidget()
            summ_widget.setStyleSheet("background: transparent;")
            summ_widget.setLayout(_grid(summary_tiles, cols=3))
            root.addWidget(summ_widget)
        else:
            root.addWidget(_empty(
                "No cart history yet — order counts are recorded each time you send items to Woolworths."
            ))

        root.addWidget(_divider())

        # ── price lows ── #
        lows = at_alltime_low + at_n_low
        root.addWidget(_section_heading(f"📉  Price Lows  ({window}d window)"))
        if lows:
            low_grid = _grid(
                [_PriceLowCard(d["name"], d["current"], d["type"], d.get("high"), d["tags"])
                 for d in lows[:6]],
                cols=3,
            )
            low_widget = QWidget()
            low_widget.setStyleSheet("background: transparent;")
            low_widget.setLayout(low_grid)
            root.addWidget(low_widget)
        else:
            root.addWidget(_empty(
                f"No items at {window}-day or all-time lows. Refresh items to start tracking history."
            ))

        root.addWidget(_divider())

        # ── price changes ── #
        if price_rises or price_drops:
            root.addWidget(_section_heading("📊  Recent Price Changes"))
            changes_row = QHBoxLayout()
            changes_row.setSpacing(SPACE_MD)

            if price_rises:
                rises_col = QVBoxLayout()
                rises_col.setSpacing(SPACE_SM)
                rises_heading = QLabel("Prices Up")
                rises_heading.setStyleSheet(
                    f"color: {t.danger}; font-size: {FS_META}px; font-weight: bold;"
                )
                rises_col.addWidget(rises_heading)
                for d in price_rises[:4]:
                    rises_col.addWidget(_ChangeCard(d["name"], d["current"], d["previous"], d["tags"]))
                rises_col.addStretch()
                rises_wrap = QWidget()
                rises_wrap.setStyleSheet("background: transparent;")
                rises_wrap.setLayout(rises_col)
                changes_row.addWidget(rises_wrap, 1)

            if price_drops:
                drops_col = QVBoxLayout()
                drops_col.setSpacing(SPACE_SM)
                drops_heading = QLabel("Prices Down")
                drops_heading.setStyleSheet(
                    f"color: {t.success}; font-size: {FS_META}px; font-weight: bold;"
                )
                drops_col.addWidget(drops_heading)
                for d in price_drops[:4]:
                    drops_col.addWidget(_ChangeCard(d["name"], d["current"], d["previous"], d["tags"]))
                drops_col.addStretch()
                drops_wrap = QWidget()
                drops_wrap.setStyleSheet("background: transparent;")
                drops_wrap.setLayout(drops_col)
                changes_row.addWidget(drops_wrap, 1)

            changes_widget = QWidget()
            changes_widget.setStyleSheet("background: transparent;")
            changes_widget.setLayout(changes_row)
            root.addWidget(changes_widget)
            root.addWidget(_divider())

        # ── recipe insights ── #
        root.addWidget(_section_heading("🍳  Recipe Insights"))
        if recipe_costs:
            rec_cards = [_RecipeCard(
                "Cheapest", recipe_costs[0]["name"], recipe_costs[0]["cost"],
                detail=f"${recipe_costs[0]['per_serving']:.2f}/serving · {recipe_costs[0]['servings']} servings",
            )]
            if len(recipe_costs) > 1:
                rec_cards.append(_RecipeCard(
                    "Most Expensive", recipe_costs[-1]["name"], recipe_costs[-1]["cost"],
                    detail=f"${recipe_costs[-1]['per_serving']:.2f}/serving · {recipe_costs[-1]['servings']} servings",
                ))
            if len(recipe_costs) >= 3:
                mid = recipe_costs[len(recipe_costs) // 2]
                rec_cards.append(_RecipeCard(
                    "Mid-range", mid["name"], mid["cost"],
                    detail=f"${mid['per_serving']:.2f}/serving",
                ))
            avg_cost = sum(r["cost"] for r in recipe_costs) / len(recipe_costs)
            closest = min(recipe_costs, key=lambda r: abs(r["cost"] - avg_cost))
            rec_cards.append(_RecipeCard(
                "Avg Recipe Cost", closest["name"], round(avg_cost, 2),
                detail=f"Closest: {closest['name']}",
            ))
            rec_widget = QWidget()
            rec_widget.setStyleSheet("background: transparent;")
            rec_widget.setLayout(_grid(rec_cards, cols=4))
            root.addWidget(rec_widget)
        else:
            root.addWidget(_empty("No recipe cost data yet."))

        # ── best recipes right now ── #
        if on_special and recipe_costs:
            special_names = {d["name"] for d in on_special}
            special_map = {d["name"]: d for d in on_special}

            # rank every recipe by savings, count, and % of ingredients on special
            recipe_rankings = []
            for rname, _ in recipe_obj.get_recipes():
                rdoc = recipe_obj.get_recipe_details(rname)
                if not rdoc:
                    continue
                ings = [i.get("item_name") for i in rdoc.get("ingredients", []) if i.get("item_name")]
                on_sp = [n for n in ings if n in special_names]
                count = len(on_sp)
                saving = sum(special_map[n]["saving"] for n in on_sp)
                pct_on_sp = len(on_sp) / len(ings) * 100 if ings else 0
                cost_entry = next((r for r in recipe_costs if r["name"] == rname), None)
                recipe_rankings.append({
                    "name": rname,
                    "count": count,
                    "saving": saving,
                    "pct_on_sp": pct_on_sp,
                    "cost": cost_entry["cost"] if cost_entry else None,
                    "per_serving": cost_entry["per_serving"] if cost_entry else None,
                    "servings": rdoc.get("servings", 1),
                })

            ranked_by_saving = sorted(recipe_rankings, key=lambda r: r["saving"], reverse=True)
            ranked_by_count = sorted(recipe_rankings, key=lambda r: r["count"], reverse=True)
            ranked_by_pct = sorted(recipe_rankings, key=lambda r: r["pct_on_sp"], reverse=True)

            best_saving_r = next((r for r in ranked_by_saving if r["saving"] > 0), None)
            most_specials_r = next((r for r in ranked_by_count if r["count"] > 0), None)
            best_pct_r = next((r for r in ranked_by_pct if r["pct_on_sp"] > 0), None)
            best_value_r = min(
                (r for r in recipe_costs if r["per_serving"]),
                key=lambda r: r["per_serving"], default=None
            )

            insight_cards = []

            if best_saving_r:
                insight_cards.append(_RecipeCard(
                    f"⭐ Best Deal  ·  {best_saving_r['count']} ingredients on special",
                    best_saving_r["name"],
                    best_saving_r["cost"] or 0.0,
                    savings=best_saving_r["saving"],
                    detail=f"{best_saving_r['servings']} servings",
                ))

            if most_specials_r and most_specials_r["name"] != (best_saving_r["name"] if best_saving_r else ""):
                insight_cards.append(_RecipeCard(
                    f"Most Specials  ·  {most_specials_r['count']} on special",
                    most_specials_r["name"],
                    most_specials_r["cost"] or 0.0,
                    savings=most_specials_r["saving"],
                    detail=f"{most_specials_r['pct_on_sp']:.0f}% of ingredients on special",
                ))

            if best_pct_r and best_pct_r["name"] not in {r._name if hasattr(r, '_name') else "" for r in insight_cards}:
                insight_cards.append(_RecipeCard(
                    f"Highest % On Special  ·  {best_pct_r['pct_on_sp']:.0f}%",
                    best_pct_r["name"],
                    best_pct_r["cost"] or 0.0,
                    savings=best_pct_r["saving"],
                    detail=f"{best_pct_r['count']} of ingredients are on special now",
                ))

            if best_value_r:
                insight_cards.append(_RecipeCard(
                    "Best Value Per Serving",
                    best_value_r["name"],
                    best_value_r["cost"],
                    detail=f"${best_value_r['per_serving']:.2f}/serving · {best_value_r['servings']} servings",
                ))

            if insight_cards:
                root.addWidget(_divider())
                root.addWidget(_section_heading("⭐  Best Recipes to Cook Right Now"))
                ig_widget = QWidget()
                ig_widget.setStyleSheet("background: transparent;")
                ig_widget.setLayout(_grid(insight_cards, cols=2))
                root.addWidget(ig_widget)

        root.addStretch()
        scroll.setWidget(container)
        return_layout.addWidget(scroll)


def _empty(msg: str) -> QLabel:
    t = theme.theme()
    lbl = QLabel(msg)
    lbl.setStyleSheet(f"color: {t.text_faint}; font-size: {FS_BODY}px; padding: 16px 0;")
    lbl.setWordWrap(True)
    return lbl
