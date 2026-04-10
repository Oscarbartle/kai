import uuid
import math
from datetime import datetime

from kai.core.io import IO
from kai.core import settings
from .recipe import Recipe
from .item import Item


# ── unit helpers ──────────────────────────────────────────────── #

_TO_BASE = {
    "g": ("g", 1),
    "kg": ("g", 1000),
    "ml": ("mL", 1),
    "l": ("mL", 1000),
    "ea": ("ea", 1),
}


def _to_base(amount, unit):
    """Convert an amount to its base unit (g, mL, or ea)."""
    key = unit.lower().strip()
    base_unit, factor = _TO_BASE.get(key, ("ea", 1))
    return amount * factor, base_unit


class ShoppingList:
    def __init__(self):
        self.io = IO(settings.data_dir() / "shopping_lists.json")

    def compute_items(self, recipe_entries: list, exclude_long_term: bool = True, extra_items: list = None):
        """Compute aggregated shopping items with units-to-buy calculation.

        extra_items: list of {"item_name": str, "units": int} for standalone items.
        """
        item_obj = Item()
        recipe_obj = Recipe()
        long_term_items = item_obj.get_long_term_items() if exclude_long_term else []

        # aggregate amounts by item (converted to base units)
        aggregated = {}
        for entry in recipe_entries:
            rname = entry["recipe_name"]
            multiplier = entry.get("multiplier", 1)
            ingredients = recipe_obj.get_scaled_ingredients(rname, multiplier)

            for ing in ingredients:
                item_name = ing.get("item_name", "")
                if item_name in long_term_items:
                    continue
                if ing.get("nominal"):
                    continue

                amount = ing.get("amount", 1) or 1
                unit = ing.get("unit", "ea")
                base_amount, base_unit = _to_base(amount, unit)

                if item_name in aggregated:
                    prev = aggregated[item_name]
                    if prev["base_unit"] == base_unit:
                        prev["total_amount"] += base_amount
                    else:
                        # incompatible units — treat as separate "ea" additions
                        prev["total_amount"] += 1
                        prev["base_unit"] = "ea"
                else:
                    details = item_obj.get_item_details(item_name)
                    price = item_obj.get_item_price(item_name, mode="per_unit")
                    tags = details.get("tags", []) if details else []
                    pkg_size, pkg_unit = item_obj.get_package_size(item_name)

                    aggregated[item_name] = {
                        "item_name": item_name,
                        "total_amount": base_amount,
                        "base_unit": base_unit,
                        "unit_price": float(price) if price else None,
                        "pkg_size": pkg_size,
                        "pkg_unit": pkg_unit,
                        "tags": tags,
                        "purchased": False,
                    }

        # add standalone extra items
        for extra in (extra_items or []):
            item_name = extra.get("item_name", "")
            if item_name in long_term_items:
                continue
            units = extra.get("units", 1)
            if item_name in aggregated:
                prev = aggregated[item_name]
                if prev["base_unit"] == "ea":
                    prev["total_amount"] += units
                else:
                    # item already aggregated by weight from recipe — just add units
                    pkg = prev["pkg_size"] or 1
                    prev["total_amount"] += pkg * units
            else:
                details = item_obj.get_item_details(item_name)
                price = item_obj.get_item_price(item_name, mode="per_unit")
                tags = details.get("tags", []) if details else []
                pkg_size, pkg_unit = item_obj.get_package_size(item_name)

                aggregated[item_name] = {
                    "item_name": item_name,
                    "total_amount": float(units),
                    "base_unit": "ea",
                    "unit_price": float(price) if price else None,
                    "pkg_size": pkg_size,
                    "pkg_unit": pkg_unit,
                    "tags": tags,
                    "purchased": False,
                }

        items = []
        for data in aggregated.values():
            total = data["total_amount"]
            base_unit = data["base_unit"]
            pkg_size = data["pkg_size"]
            pkg_unit = data["pkg_unit"]

            # calculate units to buy
            if pkg_size and pkg_unit and base_unit == pkg_unit and pkg_size > 0:
                units_needed = math.ceil(total / pkg_size)
            elif base_unit == "ea":
                units_needed = math.ceil(total)
            else:
                # no package info — fallback to 1
                units_needed = 1

            # format the amount for display
            if base_unit == "g" and total >= 1000:
                display_amount = round(total / 1000, 2)
                display_unit = "kg"
            elif base_unit == "mL" and total >= 1000:
                display_amount = round(total / 1000, 2)
                display_unit = "L"
            else:
                display_amount = round(total, 1)
                display_unit = base_unit

            data["amount"] = display_amount
            data["amount_unit"] = display_unit
            data["units_needed"] = units_needed
            data["price"] = round(data["unit_price"] * units_needed, 2) if data["unit_price"] else None

            # clean up internal fields
            del data["total_amount"]
            del data["base_unit"]
            del data["pkg_size"]
            del data["pkg_unit"]

            items.append(data)

        return items

    def compute_long_term_items(self, recipe_entries: list, extra_items: list = None):
        """Compute aggregated long-term items needed by the given recipes/extras.

        Returns the same item dicts as compute_items but only for long-term items.
        """
        item_obj = Item()
        recipe_obj = Recipe()
        long_term_names = set(item_obj.get_long_term_items())

        aggregated = {}
        for entry in recipe_entries:
            rname = entry["recipe_name"]
            multiplier = entry.get("multiplier", 1)
            ingredients = recipe_obj.get_scaled_ingredients(rname, multiplier)

            for ing in ingredients:
                item_name = ing.get("item_name", "")
                if item_name not in long_term_names:
                    continue

                if ing.get("nominal"):
                    base_amount, base_unit = 1, "ea"
                else:
                    amount = ing.get("amount", 1) or 1
                    unit = ing.get("unit", "ea")
                    base_amount, base_unit = _to_base(amount, unit)

                if item_name in aggregated:
                    prev = aggregated[item_name]
                    if prev["base_unit"] == base_unit:
                        prev["total_amount"] += base_amount
                    else:
                        prev["total_amount"] += 1
                        prev["base_unit"] = "ea"
                else:
                    details = item_obj.get_item_details(item_name)
                    price = item_obj.get_item_price(item_name, mode="per_unit")
                    tags = details.get("tags", []) if details else []
                    pkg_size, pkg_unit = item_obj.get_package_size(item_name)

                    aggregated[item_name] = {
                        "item_name": item_name,
                        "total_amount": base_amount,
                        "base_unit": base_unit,
                        "unit_price": float(price) if price else None,
                        "pkg_size": pkg_size,
                        "pkg_unit": pkg_unit,
                        "tags": tags,
                        "purchased": False,
                    }

        # extra items that are long-term
        for extra in (extra_items or []):
            item_name = extra.get("item_name", "")
            if item_name not in long_term_names:
                continue
            units = extra.get("units", 1)
            if item_name in aggregated:
                prev = aggregated[item_name]
                if prev["base_unit"] == "ea":
                    prev["total_amount"] += units
                else:
                    pkg = prev["pkg_size"] or 1
                    prev["total_amount"] += pkg * units
            else:
                details = item_obj.get_item_details(item_name)
                price = item_obj.get_item_price(item_name, mode="per_unit")
                tags = details.get("tags", []) if details else []
                pkg_size, pkg_unit = item_obj.get_package_size(item_name)

                aggregated[item_name] = {
                    "item_name": item_name,
                    "total_amount": float(units),
                    "base_unit": "ea",
                    "unit_price": float(price) if price else None,
                    "pkg_size": pkg_size,
                    "pkg_unit": pkg_unit,
                    "tags": tags,
                    "purchased": False,
                }

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

            if base_unit == "g" and total >= 1000:
                display_amount = round(total / 1000, 2)
                display_unit = "kg"
            elif base_unit == "mL" and total >= 1000:
                display_amount = round(total / 1000, 2)
                display_unit = "L"
            else:
                display_amount = round(total, 1)
                display_unit = base_unit

            data["amount"] = display_amount
            data["amount_unit"] = display_unit
            data["units_needed"] = units_needed
            data["price"] = round(data["unit_price"] * units_needed, 2) if data["unit_price"] else None

            del data["total_amount"]
            del data["base_unit"]
            del data["pkg_size"]
            del data["pkg_unit"]

            items.append(data)

        return items

    def compute_nominal_items(self, recipe_entries: list):
        """Compute items marked as nominal — always 1 unit each, excluded from main total."""
        item_obj = Item()
        recipe_obj = Recipe()

        aggregated = {}
        for entry in recipe_entries:
            rname = entry["recipe_name"]
            ingredients = recipe_obj.get_scaled_ingredients(rname, 1)

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

    def generate(self, recipe_entries: list, exclude_long_term: bool = True, name: str = "", extra_items: list = None, lt_missing: list = None):
        """Generate and save a shopping list from recipes and extra items.

        lt_missing: list of long-term item names the user needs to buy.
        """
        items = self.compute_items(recipe_entries, exclude_long_term, extra_items)

        # add long-term items the user doesn't have
        if lt_missing:
            lt_items = self.compute_long_term_items(recipe_entries, extra_items)
            for lt_item in lt_items:
                if lt_item["item_name"] in lt_missing:
                    items.append(lt_item)

        list_id = str(uuid.uuid4())
        recipe_names = [e["recipe_name"] + (f" x{e['multiplier']}" if e.get("multiplier", 1) > 1 else "")
                        for e in recipe_entries]

        if not name:
            name = ", ".join(recipe_names)

        self.io.create(list_id, {
            "name": name,
            "recipes": recipe_names,
            "recipe_entries": recipe_entries,
            "extra_items": extra_items or [],
            "lt_missing": lt_missing or [],
            "items": items,
            "date_generated": datetime.now().isoformat()
        }, overwrite=True)

        return list_id

    def get_list(self, list_id: str):
        return self.io.get(list_id)

    def get_all_lists(self):
        """Returns list of (name, list_id, date) sorted newest first."""
        all_lists = self.io.all()
        result = []
        for lid, data in all_lists.items():
            name = data.get("name", ", ".join(data.get("recipes", [])))
            date = data.get("date_generated", "")
            result.append((name, lid, date))
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

    def export_text(self, list_id: str):
        """Export shopping list as formatted text"""
        list_data = self.get_list(list_id)
        if not list_data:
            return ""

        lines = [f"Shopping List — {list_data.get('name', '')}"]
        lines.append(f"Generated: {list_data.get('date_generated', '')[:10]}")
        lines.append("=" * 40)

        # group by tag
        grouped = {}
        for item in list_data.get("items", []):
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

        return "\n".join(lines)
