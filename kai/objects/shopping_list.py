import uuid
import math
from datetime import datetime

from kai.core.io import IO
from kai.core import settings
from kai.utils.units import to_base, format_amount
from .recipe import Recipe
from .item import Item


class ShoppingList:
    def __init__(self):
        self.io = IO(settings.data_dir() / "shopping_lists.json")

    # ── private helpers ───────────────────────────────────────────── #

    def _load_item_meta(self, item_name: str, item_obj: Item) -> dict:
        """Return the pricing/sizing/tag metadata dict for a single item."""
        details = item_obj.get_item_details(item_name)
        price = item_obj.get_item_price(item_name, mode="per_unit")
        tags = details.get("tags", []) if details else []
        pkg_size, pkg_unit = item_obj.get_package_size(item_name)
        return {
            "item_name": item_name,
            "unit_price": float(price) if price else None,
            "pkg_size": pkg_size,
            "pkg_unit": pkg_unit,
            "tags": tags,
            "purchased": False,
        }

    def _add_to_aggregated(
        self,
        aggregated: dict,
        item_name: str,
        base_amount: float,
        base_unit: str,
        item_obj: Item,
        from_recipe: bool = False,
    ):
        """Accumulate *base_amount* of *item_name* into the *aggregated* dict."""
        if item_name in aggregated:
            prev = aggregated[item_name]
            if prev["base_unit"] == base_unit:
                prev["total_amount"] += base_amount
            else:
                # Incompatible units (e.g. g from one recipe, ea from another)
                # — fall back to counting whole units.
                prev["total_amount"] += 1
                prev["base_unit"] = "ea"
            if from_recipe:
                prev["source_recipe"] = True
        else:
            meta = self._load_item_meta(item_name, item_obj)
            aggregated[item_name] = {
                **meta,
                "total_amount": base_amount,
                "base_unit": base_unit,
                "source_recipe": from_recipe,
                "source_manual": False,
                "manual_units": 0,
            }

    def _aggregate_ingredients(
        self,
        recipe_entries: list,
        item_names_filter: set | None,
        item_obj: Item,
        recipe_obj: Recipe,
        include_nominal: bool = False,
    ) -> dict:
        """Aggregate recipe ingredients into a base-unit dict.

        *item_names_filter*: if given, only include items whose name is in this
        set.  If None, include all items (except long-term when called from
        compute_items).
        """
        aggregated: dict = {}

        for entry in recipe_entries:
            multiplier = entry.get("multiplier", 1)
            ingredients = recipe_obj.get_scaled_ingredients(
                entry["recipe_name"], multiplier
            )
            for ing in ingredients:
                item_name = ing.get("item_name", "")
                if not item_name:
                    continue
                if item_names_filter is not None and item_name not in item_names_filter:
                    continue
                if ing.get("nominal"):
                    if not include_nominal:
                        continue
                    base_amount, base_unit = 1.0, "ea"
                else:
                    amount = ing.get("amount", 1) or 1
                    unit = ing.get("unit", "ea")
                    base_amount, base_unit = to_base(amount, unit)

                self._add_to_aggregated(
                    aggregated,
                    item_name,
                    base_amount,
                    base_unit,
                    item_obj,
                    from_recipe=True,
                )

        return aggregated

    def _aggregate_extra_items(
        self,
        aggregated: dict,
        extra_items: list,
        item_names_filter: set | None,
        item_obj: Item,
    ):
        """Merge standalone extra items into an existing *aggregated* dict."""
        for extra in (extra_items or []):
            item_name = extra.get("item_name", "")
            if not item_name:
                continue
            if item_names_filter is not None and item_name not in item_names_filter:
                continue
            units = extra.get("units", 1)
            if item_name in aggregated:
                prev = aggregated[item_name]
                prev["source_manual"] = True
                prev["manual_units"] = int(prev.get("manual_units", 0) + units)
                if prev["base_unit"] == "ea":
                    prev["total_amount"] += units
                else:
                    # Already have a weight total — add whole packages' worth.
                    pkg = prev["pkg_size"] or 1
                    prev["total_amount"] += pkg * units
            else:
                meta = self._load_item_meta(item_name, item_obj)
                aggregated[item_name] = {
                    **meta,
                    "total_amount": float(units),
                    "base_unit": "ea",
                    "source_recipe": False,
                    "source_manual": True,
                    "manual_units": int(units),
                }

    def _finalise_aggregated(self, aggregated: dict) -> list[dict]:
        """Convert internal aggregation dicts to display-ready item dicts."""
        items = []
        for data in aggregated.values():
            total = data["total_amount"]
            base_unit = data["base_unit"]
            pkg_size = data["pkg_size"]
            pkg_unit = data["pkg_unit"]

            if pkg_size and pkg_unit and base_unit == pkg_unit and pkg_size > 0:
                units_needed = math.ceil(total / pkg_size)
            elif base_unit == "ea":
                units_needed = math.ceil(total)
            else:
                units_needed = 1

            display_amount, display_unit = format_amount(total, base_unit)

            item = dict(data)
            item["amount"] = display_amount
            item["amount_unit"] = display_unit
            item["units_needed"] = units_needed
            item["price"] = (
                round(data["unit_price"] * units_needed, 2)
                if data["unit_price"]
                else None
            )
            # Remove aggregation-internal fields before returning
            for key in ("total_amount", "base_unit", "pkg_size", "pkg_unit"):
                item.pop(key, None)
            items.append(item)
        return items

    # ── public computation API ────────────────────────────────────── #

    def compute_items(
        self,
        recipe_entries: list,
        exclude_long_term: bool = True,
        extra_items: list = None,
    ) -> list[dict]:
        """Aggregate short-term shopping items from recipes and extra items."""
        item_obj = Item()
        recipe_obj = Recipe()

        excluded = set(item_obj.get_long_term_items()) if exclude_long_term else set()
        all_names = set(item_obj.get_item_names())
        # Include everything that isn't long-term
        allowed = all_names - excluded if exclude_long_term else None

        aggregated = self._aggregate_ingredients(
            recipe_entries, allowed, item_obj, recipe_obj
        )
        self._aggregate_extra_items(aggregated, extra_items, allowed, item_obj)
        return self._finalise_aggregated(aggregated)

    def compute_long_term_items(
        self,
        recipe_entries: list,
        extra_items: list = None,
    ) -> list[dict]:
        """Aggregate long-term items required by the given recipes and extras."""
        item_obj = Item()
        recipe_obj = Recipe()
        long_term = set(item_obj.get_long_term_items())

        aggregated = self._aggregate_ingredients(
            recipe_entries, long_term, item_obj, recipe_obj, include_nominal=True
        )
        self._aggregate_extra_items(aggregated, extra_items, long_term, item_obj)
        return self._finalise_aggregated(aggregated)

    def compute_nominal_items(self, recipe_entries: list) -> list[dict]:
        """Return nominal items (always 1 unit each, excluded from totals)."""
        item_obj = Item()
        recipe_obj = Recipe()
        aggregated: dict = {}

        for entry in recipe_entries:
            ingredients = recipe_obj.get_scaled_ingredients(
                entry["recipe_name"], 1
            )
            for ing in ingredients:
                if not ing.get("nominal"):
                    continue
                item_name = ing.get("item_name", "")
                if not item_name or item_name in aggregated:
                    continue
                price = item_obj.get_item_price(item_name, mode="per_unit")
                aggregated[item_name] = {
                    "item_name": item_name,
                    "units_needed": 1,
                    "price": round(float(price), 2) if price else None,
                }

        return list(aggregated.values())

    # ── persistence ───────────────────────────────────────────────── #

    def generate(
        self,
        recipe_entries: list,
        exclude_long_term: bool = True,
        name: str = "",
        extra_items: list = None,
        lt_missing: list = None,
    ) -> str:
        """Generate, persist, and return the ID of a new shopping list."""
        items = self.compute_items(recipe_entries, exclude_long_term, extra_items)

        if lt_missing:
            lt_items = self.compute_long_term_items(recipe_entries, extra_items)
            items.extend(
                lt for lt in lt_items if lt["item_name"] in lt_missing
            )

        list_id = str(uuid.uuid4())
        recipe_names = [
            e["recipe_name"] + (f" x{e['multiplier']}" if e.get("multiplier", 1) > 1 else "")
            for e in recipe_entries
        ]
        self.io.create(list_id, {
            "name": name or ", ".join(recipe_names),
            "recipes": recipe_names,
            "recipe_entries": recipe_entries,
            "extra_items": extra_items or [],
            "lt_missing": lt_missing or [],
            "items": items,
            "date_generated": datetime.now().isoformat(),
        }, overwrite=True)
        return list_id

    def get_list(self, list_id: str) -> dict | None:
        return self.io.get(list_id)

    def get_all_lists(self) -> list[tuple[str, str, str]]:
        """Return ``(name, list_id, date)`` tuples sorted newest first."""
        result = [
            (
                data.get("name", ", ".join(data.get("recipes", []))),
                lid,
                data.get("date_generated", ""),
            )
            for lid, data in self.io.all().items()
        ]
        result.sort(key=lambda x: x[2], reverse=True)
        return result

    def delete_list(self, list_id: str):
        self.io.delete(list_id)

    def mark_purchased(self, list_id: str, item_name: str, purchased: bool = True):
        data = self.io.all()
        if list_id not in data:
            return
        for item in data[list_id].get("items", []):
            if item["item_name"] == item_name:
                item["purchased"] = purchased
                break
        self.io.write(data)

    # ── export ────────────────────────────────────────────────────── #

    def export_text(self, list_id: str) -> str:
        """Format the shopping list as plain text (for clipboard export)."""
        list_data = self.get_list(list_id)
        if not list_data:
            return ""

        lines = [
            f"Shopping List — {list_data.get('name', '')}",
            f"Generated: {list_data.get('date_generated', '')[:10]}",
            "=" * 40,
        ]

        # group items by first tag
        grouped: dict[str, list] = {}
        for item in list_data.get("items", []):
            tag = (item.get("tags") or ["Other"])[0]
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
                lines.append(
                    f"  {check} {item['item_name']}{qty_str}{amount_str}{price_str}"
                )
                if item.get("price"):
                    total += item["price"]

        lines += [f"\n{'=' * 40}", f"Estimated Total: ${round(total, 2)}"]
        return "\n".join(lines)
