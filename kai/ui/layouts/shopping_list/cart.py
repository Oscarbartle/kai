import json
import webbrowser

from kai.objects.recipe import Recipe
from kai.objects.item import Item
from kai.objects.shopping_list import ShoppingList
from kai.core.backend import get_recipe, get_item, get_shopping_list
from kai.ui import theme
from kai.ui.refresh_worker import run_refresh
from kai.ui.layouts.shopping_list.cards import CartEntry, ExtraItemEntry
from kai.ui.widgets.shopping_item import ShoppingItem
from kai.core import settings as app_settings
from kai.ui.tokens import (
    SPACE_XS, SPACE_SM, SPACE_MD, SPACE_LG,
    RADIUS_SM, RADIUS_MD, BORDER_W,
    H_ROW,
    FS_BODY, FS_META, FS_TINY,
    FW_BOLD, FW_MEDIUM,
)

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QSplitter,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QCheckBox,
    QApplication,
    QFrame,
)
from PySide6.QtGui import QCursor
from PySide6.QtCore import Qt


class ShoppingListCartMixin:
    # ── right panel: cart + generated list + long-term ─────────── #

    def _build_right_panel(self):
        self.right_panel = QWidget()
        self.right_panel.setObjectName("page_panel")
        right_layout = QVBoxLayout(self.right_panel)
        right_layout.setContentsMargins(SPACE_LG, SPACE_LG, SPACE_LG, SPACE_LG)
        right_layout.setSpacing(SPACE_SM)

        t = theme.theme()

        # ── header ───────────────────────────────────────────── #
        cart_label = QLabel("Shopping List")
        cart_label.setProperty("role", "heading")
        right_layout.addWidget(cart_label)

        top_row = QHBoxLayout()
        top_row.setSpacing(SPACE_SM)

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("List name (optional)")
        top_row.addWidget(self.name_input, 1)

        self.save_button = QPushButton("Save")
        self.save_button.setProperty("btn", "primary")
        self.save_button.setEnabled(False)
        top_row.addWidget(self.save_button)

        self.export_button = QPushButton("Copy")
        self.export_button.setProperty("btn", "secondary")
        self.export_button.setToolTip("Copy list to clipboard")
        self.export_button.setEnabled(False)
        top_row.addWidget(self.export_button)

        self.links_button = QPushButton("Cart")
        self.links_button.setProperty("btn", "secondary")
        self.links_button.setEnabled(False)
        self.links_button.setToolTip("Add items to Woolworths trolley")
        top_row.addWidget(self.links_button)

        self.clear_button = QPushButton("Clear")
        self.clear_button.setProperty("btn", "secondary")
        self.clear_button.setEnabled(False)
        self.clear_button.setToolTip("Clear the current shopping list")
        top_row.addWidget(self.clear_button)

        right_layout.addLayout(top_row)

        # ── vertical splitter: Cart / Shopping List / Long-term ── #
        self.v_splitter = QSplitter(Qt.Orientation.Vertical)
        self.v_splitter.setChildrenCollapsible(False)

        # — cart pane —
        cart_pane = QWidget()
        cart_pane.setMinimumHeight(80)
        cart_pane_layout = QVBoxLayout(cart_pane)
        cart_pane_layout.setContentsMargins(0, SPACE_SM, 0, 0)
        cart_pane_layout.setSpacing(SPACE_SM)

        cart_header = QHBoxLayout()
        cart_heading = QLabel("Cart")
        cart_heading.setStyleSheet(
            f"color: {t.text_dim}; font-size: {FS_META}px; font-weight: {FW_BOLD}; "
            "letter-spacing: 0.6px; text-transform: uppercase;"
        )
        cart_header.addWidget(cart_heading)
        cart_header.addStretch()
        self._cart_count_label = QLabel("")
        self._cart_count_label.setStyleSheet(f"color: {t.text_faint}; font-size: {FS_META}px;")
        cart_header.addWidget(self._cart_count_label)
        cart_pane_layout.addLayout(cart_header)

        self.cart_scroll = QScrollArea()
        self.cart_scroll.setWidgetResizable(True)
        self.cart_scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        cart_scroll_widget = QWidget()
        cart_scroll_widget.setStyleSheet("background: transparent;")
        self.cart_layout = QVBoxLayout(cart_scroll_widget)
        self.cart_layout.setContentsMargins(0, 2, 0, 2)
        self.cart_layout.setSpacing(4)
        self.cart_layout.addStretch()
        self.cart_scroll.setWidget(cart_scroll_widget)
        self.empty_cart_label = QLabel("Add recipes or items to get started")
        self.empty_cart_label.setProperty("role", "faint")
        self.cart_layout.insertWidget(0, self.empty_cart_label)
        cart_pane_layout.addWidget(self.cart_scroll, 1)

        # — shopping list pane —
        list_pane = QWidget()
        list_pane.setMinimumHeight(80)
        list_pane_layout = QVBoxLayout(list_pane)
        list_pane_layout.setContentsMargins(0, SPACE_SM, 0, 0)
        list_pane_layout.setSpacing(SPACE_SM)

        list_header = QHBoxLayout()
        list_heading = QLabel("Shopping List")
        list_heading.setStyleSheet(
            f"color: {t.text_dim}; font-size: {FS_META}px; font-weight: {FW_BOLD}; "
            "letter-spacing: 0.6px; text-transform: uppercase;"
        )
        list_header.addWidget(list_heading)
        list_header.addStretch()
        self.serves_label = QLabel("")
        self.serves_label.setStyleSheet(f"color: {t.text_dim}; font-size: {FS_META}px;")
        list_header.addWidget(self.serves_label)
        self.count_label = QLabel("")
        self.count_label.setProperty("role", "dim")
        list_header.addWidget(self.count_label)
        self.total_label = QLabel("")
        self.total_label.setProperty("role", "price")
        list_header.addWidget(self.total_label)
        list_pane_layout.addLayout(list_header)

        self.items_scroll = QScrollArea()
        self.items_scroll.setWidgetResizable(True)
        self.items_scroll.setStyleSheet("QScrollArea { border: none; }")
        items_scroll_widget = QWidget()
        items_scroll_widget.setStyleSheet("background: transparent;")
        self.items_scroll_layout = QVBoxLayout(items_scroll_widget)
        self.items_scroll_layout.setContentsMargins(0, SPACE_XS, 0, SPACE_XS)
        self.items_scroll_layout.setSpacing(4)
        self.items_scroll_layout.addStretch()
        self.items_scroll.setWidget(items_scroll_widget)
        list_pane_layout.addWidget(self.items_scroll, 1)
        self.v_splitter.addWidget(list_pane)
        self.v_splitter.addWidget(cart_pane)

        # — long-term pane —
        lt_pane = QWidget()
        lt_pane.setMinimumHeight(60)
        lt_pane_layout = QVBoxLayout(lt_pane)
        lt_pane_layout.setContentsMargins(0, SPACE_SM, 0, 0)
        lt_pane_layout.setSpacing(SPACE_SM)

        lt_header = QHBoxLayout()
        lt_heading = QLabel("Long-term Items")
        lt_heading.setStyleSheet(
            f"color: {t.text_dim}; font-size: {FS_META}px; font-weight: {FW_BOLD}; "
            "letter-spacing: 0.6px; text-transform: uppercase;"
        )
        lt_header.addWidget(lt_heading)
        lt_header.addStretch()
        lt_hint = QLabel("Uncheck to add to list")
        lt_hint.setStyleSheet(f"color: {t.text_faint}; font-size: {FS_META}px;")
        lt_header.addWidget(lt_hint)
        lt_pane_layout.addLayout(lt_header)

        self.lt_scroll = QScrollArea()
        self.lt_scroll.setWidgetResizable(True)
        self.lt_scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        lt_scroll_widget = QWidget()
        lt_scroll_widget.setStyleSheet("background: transparent;")
        self.lt_layout = QVBoxLayout(lt_scroll_widget)
        self.lt_layout.setContentsMargins(0, 2, 0, 2)
        self.lt_layout.setSpacing(4)
        self.lt_layout.addStretch()
        self.lt_scroll.setWidget(lt_scroll_widget)
        self.lt_empty_label = QLabel("No long-term items needed")
        self.lt_empty_label.setProperty("role", "faint")
        self.lt_layout.insertWidget(0, self.lt_empty_label)
        lt_pane_layout.addWidget(self.lt_scroll, 1)
        self.v_splitter.addWidget(lt_pane)

        self.v_splitter.setHandleWidth(6)
        self.v_splitter.setStretchFactor(0, 1)
        self.v_splitter.setStretchFactor(1, 3)
        self.v_splitter.setStretchFactor(2, 1)

        from PySide6.QtCore import QTimer
        QTimer.singleShot(0, lambda: self.v_splitter.setSizes([400, 150, 120]))

        right_layout.addWidget(self.v_splitter, 1)
        self.h_splitter.insertWidget(1, self.right_panel)
        self.h_splitter.setStretchFactor(1, 3)

    def _divider(self) -> QWidget:
        sep = QWidget()
        sep.setFixedHeight(1)
        sep.setStyleSheet(theme.divider_line_css())
        return sep

    # ── cart management ────────────────────────────────────────── #

    def _add_extra_item(self, item_name, units=1, weight_kg=None):
        item_obj = get_item()
        if item_name in item_obj.get_long_term_items():
            self.lt_have[item_name] = False

        for entry in self.extra_items:
            if entry["item_name"] == item_name:
                if weight_kg is not None:
                    entry["weight_kg"] = round(entry.get("weight_kg", 0) + weight_kg, 3)
                else:
                    entry["units"] = entry.get("units", 0) + units
                self._refresh_cart()
                return

        if weight_kg is not None:
            self.extra_items.append({"item_name": item_name, "weight_kg": round(weight_kg, 3)})
        else:
            self.extra_items.append({"item_name": item_name, "units": units})
        self._refresh_cart()

    def _refresh_recipe_metadata(self, recipe_name):
        doc = get_recipe().get_recipe_details(recipe_name)
        if not doc:
            return
        names = [ing.get("item_name") for ing in doc.get("ingredients", []) if ing.get("item_name")]
        run_refresh(names, on_done=self.state.items_updated, delay=2.0)

    def _add_recipe_to_cart(self, recipe_name, multiplier):
        self._refresh_recipe_metadata(recipe_name)
        for entry in self.recipe_entries:
            if entry["recipe_name"] == recipe_name:
                entry["multiplier"] += multiplier
                self._refresh_cart()
                return
        self.recipe_entries.append({"recipe_name": recipe_name, "multiplier": multiplier})
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
        # clear existing cart widgets (keep stretch at end)
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
            self.cart_layout.addStretch()
            self.save_button.setEnabled(False)
            self.clear_button.setEnabled(False)
            self._cart_count_label.setText("")
        else:
            total = len(self.recipe_entries) + len(self.extra_items)
            self._cart_count_label.setText(
                f"{len(self.recipe_entries)} recipe{'s' if len(self.recipe_entries) != 1 else ''}"
                + (f" · {len(self.extra_items)} item{'s' if len(self.extra_items) != 1 else ''}"
                   if self.extra_items else "")
            )

            for entry in self.recipe_entries:
                card = CartEntry(entry["recipe_name"], entry["multiplier"], self._remove_from_cart)
                self.cart_layout.addWidget(card)

            for entry in self.extra_items:
                card = ExtraItemEntry(
                    entry["item_name"],
                    entry.get("units", 1),
                    self._remove_extra_item,
                    weight_kg=entry.get("weight_kg"),
                )
                self.cart_layout.addWidget(card)

            self.cart_layout.addStretch()
            self.save_button.setEnabled(True)
            self.clear_button.setEnabled(True)

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

        recipe_obj = get_recipe()
        total_servings = 0
        for entry in self.recipe_entries:
            doc = recipe_obj.get_recipe_details(entry["recipe_name"])
            base = doc.get("servings", 1) if doc else 1
            total_servings += base * entry.get("multiplier", 1)
        self.serves_label.setText(f"Serves {total_servings}  ·" if total_servings > 0 else "")

        sl = get_shopping_list()
        try:
            self.preview_items = sl.compute_items(self.recipe_entries, True, self.extra_items)
            self.lt_items = sl.compute_long_term_items(self.recipe_entries, self.extra_items)
        except NotImplementedError:
            # Remote mode: item computation happens server-side on generate.
            self.preview_items = []
            self.lt_items = []

        lt_names = {item["item_name"] for item in self.lt_items}
        self.lt_have = {k: v for k, v in self.lt_have.items() if k in lt_names}

        self._render_lt_section()

        for lt_item in self.lt_items:
            name = lt_item["item_name"]
            if not self.lt_have.get(name, True):
                self.preview_items.append(lt_item)

        self._render_preview()
        self.export_button.setEnabled(True)
        self.links_button.setEnabled(True)

    def _render_lt_section(self):
        while self.lt_layout.count():
            child = self.lt_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        if not self.lt_items:
            self.lt_empty_label = QLabel("No long-term items needed")
            self.lt_empty_label.setProperty("role", "faint")
            self.lt_layout.addWidget(self.lt_empty_label)
            self.lt_layout.addStretch()
            return

        t = theme.theme()

        for lt_item in self.lt_items:
            name = lt_item["item_name"]
            have = self.lt_have.get(name, True)

            row = QWidget()
            row.setObjectName("lt_check_row")
            row.setFixedHeight(H_ROW)
            row.setStyleSheet(theme.surface_row_css("lt_check_row", radius=RADIUS_SM))
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(SPACE_SM, 0, SPACE_SM, 0)
            row_layout.setSpacing(SPACE_SM)

            cb = QCheckBox()
            cb.setChecked(have)
            cb.setToolTip("I have this — uncheck to add to shopping list")
            cb.setStyleSheet(theme.checkbox_css())
            cb.stateChanged.connect(lambda state, n=name: self._on_lt_toggled(n, bool(state)))
            row_layout.addWidget(cb)

            name_label = QLabel(name)
            style = (
                f"color: {t.text_faint}; text-decoration: line-through;"
                if have else
                f"color: {t.text};"
            )
            name_label.setStyleSheet(f"{style} font-size: {FS_BODY}px;")
            row_layout.addWidget(name_label, 1)

            units = lt_item.get("units_needed", 1)
            if units > 1:
                qty_label = QLabel(f"x{units}")
                qty_label.setStyleSheet(
                    f"color: {t.text}; font-size: {FS_BODY}px; font-weight: {FW_BOLD};"
                )
                row_layout.addWidget(qty_label)

            amount = lt_item.get("amount")
            amount_unit = lt_item.get("amount_unit", "")
            if amount and amount_unit and amount_unit != "ea":
                amt = int(amount) if amount == int(amount) else amount
                amt_label = QLabel(f"{amt}{amount_unit}")
                amt_label.setStyleSheet(f"color: {t.text_dim}; font-size: {FS_META}px;")
                row_layout.addWidget(amt_label)

            price = lt_item.get("price")
            if price:
                price_label = QLabel(f"${price}")
                price_label.setStyleSheet(f"color: {t.accent}; font-size: {FS_META}px;")
                row_layout.addWidget(price_label)

            self.lt_layout.addWidget(row)

        self.lt_layout.addStretch()

    def _on_lt_toggled(self, item_name, have):
        self.lt_have[item_name] = have
        self._auto_render()
        self._save_draft()

    def _render_preview(self):
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
                spacer.setFixedHeight(SPACE_SM)
                spacer.setStyleSheet("background: transparent;")
                self.items_scroll_layout.addWidget(spacer)

            tag_label = QLabel(tag)
            tag_label.setStyleSheet(
                f"color: {t.text_dim}; font-size: {FS_META}px; font-weight: {FW_BOLD}; "
                f"padding: {SPACE_XS}px 0px 2px 2px;"
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

        lt_not_in_list = 0.0
        preview_names = {it["item_name"] for it in self.preview_items}
        for lt_item in self.lt_items:
            if lt_item.get("price") and lt_item["item_name"] not in preview_names:
                lt_not_in_list += lt_item["price"]

        self.items_scroll_layout.addStretch()

        all_lt = lt_in_list + lt_not_in_list
        if all_lt > 0 and round(all_lt, 2) != 0:
            label = (
                f"  <span style='color:{t.text_dim};font-size:{FS_META}px;'>"
                f"(${round(total + all_lt, 2)} w/LT)</span>&nbsp;&nbsp;&nbsp;&nbsp;"
                f"Est. Total: ${round(total + lt_in_list, 2)}"
            )
        else:
            label = f"  Est. Total: ${round(total + lt_in_list, 2)}"
        self.total_label.setText(label)
        self.count_label.setText(f"{count} items")

    def _on_save(self):
        if not self.recipe_entries and not self.extra_items:
            return

        name = self.name_input.text().strip()
        lt_missing = [n for n, have in self.lt_have.items() if not have]
        self.current_list_id = get_shopping_list().generate(
            self.recipe_entries,
            True,
            name,
            self.extra_items,
            lt_missing=lt_missing,
        )
        self.name_input.clear()
        self.state.new_shopping_list.emit()
        self._clear_draft()

    def _on_clear_list(self):
        self.recipe_entries = []
        self.extra_items = []
        self.preview_items = []
        self.lt_items = []
        self.lt_have = {}
        self.current_list_id = None
        self.name_input.clear()
        self._refresh_cart()
        self._clear_draft()

    def _on_item_toggled(self, item_name: str, purchased: bool):
        for item in self.preview_items:
            if item["item_name"] == item_name:
                item["purchased"] = purchased
                break

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
                check = "✓" if item.get("purchased") else "□"
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
        if not self.preview_items:
            return

        from kai.core.woolworths_cart import get_session, check_auth, start_cart_worker
        from kai.ui.widgets.cart_confirm_dialog import CartConfirmDialog, CartProgressDialog
        from kai.ui.widgets.lt_cart_wizard import LtCartWizard

        item_obj = get_item()

        # ── Step 1: long-term items wizard ───────────────────────── #
        extra_lt_items = []
        if self.lt_items:
            wizard = LtCartWizard(self.lt_items, parent=self)
            if wizard.exec() != LtCartWizard.DialogCode.Accepted:
                return
            extra_lt_items = wizard.selected_items

        # ── Step 2: build cart items list ────────────────────────── #
        all_items = list(self.preview_items) + [
            it for it in extra_lt_items
            if not any(p["item_name"] == it["item_name"] for p in self.preview_items)
        ]

        cart_items = []
        for item in all_items:
            details = item_obj.get_item_details(item["item_name"])
            stock_code = details.get("stock_code") if details else None
            cart_items.append(
                {
                    "name": item["item_name"],
                    "stock_code": stock_code,
                    "qty": item.get("units_needed", 1),
                    "units_needed": item.get("units_needed", 1),
                    "price": item.get("price"),
                }
            )

        confirm = CartConfirmDialog(cart_items, parent=self)
        if confirm.exec() != CartConfirmDialog.DialogCode.Accepted:
            return

        accepted = confirm.accepted_items
        if not accepted:
            return

        # record order history (once per item per day)
        from kai.objects.order_history import OrderHistory
        OrderHistory().record([i["name"] for i in accepted])

        session = get_session()
        if session is None or not check_auth(session):
            from PySide6.QtWidgets import QMessageBox

            QMessageBox.warning(
                self,
                "Not logged in",
                "Could not find a Woolworths session in your browser.\n\n"
                "Please log in to woolworths.co.nz in your browser, then try again.\n\n"
                "You can change your browser in Settings.",
            )
            for item in accepted:
                webbrowser.open(
                    f"https://www.woolworths.co.nz/shop/productdetails?stockcode={item['stock_code']}"
                )
            return

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
