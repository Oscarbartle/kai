"""HTTP client for the /shopping-lists API endpoints."""
from __future__ import annotations

from kai.clients.http import get_session, base_url


class ShoppingListClient:
    def __init__(self):
        pass  # no caching — shopping lists change frequently across devices

    # ── etag helper ───────────────────────────────────────────────── #

    def _get_etag(self, list_id: str) -> str:
        s = get_session()
        r = s.get(f"{base_url()}/shopping-lists/{list_id}")
        r.raise_for_status()
        return r.json().get("etag", "")

    # ── query API ─────────────────────────────────────────────────── #

    def get_all_lists(self) -> list[tuple[str, str, str, str]]:
        """GET /shopping-lists, return (name, id, date, type) tuples sorted newest first."""
        s = get_session()
        r = s.get(f"{base_url()}/shopping-lists")
        r.raise_for_status()
        result = []
        for item in r.json():
            result.append((
                item.get("name", ""),
                item.get("id", ""),
                item.get("date_generated", ""),
                item.get("type", "generated"),
            ))
        result.sort(key=lambda x: x[2], reverse=True)
        return result

    def get_list(self, list_id: str) -> dict | None:
        """GET /shopping-lists/{id}."""
        s = get_session()
        r = s.get(f"{base_url()}/shopping-lists/{list_id}")
        if r.status_code == 404:
            return None
        r.raise_for_status()
        data = r.json()
        # strip api-only fields
        return {k: v for k, v in data.items() if k not in ("id", "etag")}

    # ── mutation API ──────────────────────────────────────────────── #

    def create_freeform(self, name: str) -> str:
        """POST /shopping-lists, return list_id."""
        s = get_session()
        r = s.post(f"{base_url()}/shopping-lists", json={"name": name})
        r.raise_for_status()
        return r.json()["id"]

    def generate(
        self,
        recipe_entries: list,
        exclude_long_term: bool = True,
        name: str = "",
        extra_items: list = None,
        lt_missing: list = None,
    ) -> str:
        """POST /shopping-lists/generate, return list_id."""
        s = get_session()
        r = s.post(f"{base_url()}/shopping-lists/generate", json={
            "recipe_entries": recipe_entries or [],
            "exclude_long_term": exclude_long_term,
            "name": name or "",
            "extra_items": extra_items or [],
            "lt_missing": lt_missing or [],
        })
        r.raise_for_status()
        return r.json()["id"]

    def regenerate(
        self,
        list_id: str,
        recipe_entries: list,
        exclude_long_term: bool = True,
        name: str = "",
        extra_items: list = None,
        lt_missing: list = None,
    ) -> str:
        """POST /shopping-lists/{id}/regenerate, update in place and return list_id."""
        etag = self._get_etag(list_id)
        s = get_session()
        r = s.post(f"{base_url()}/shopping-lists/{list_id}/regenerate", json={
            "recipe_entries": recipe_entries or [],
            "exclude_long_term": exclude_long_term,
            "name": name or "",
            "extra_items": extra_items or [],
            "lt_missing": lt_missing or [],
        }, headers={"If-Match": f'"{etag}"'})
        if r.status_code == 412:
            etag = self._get_etag(list_id)
            r = s.post(f"{base_url()}/shopping-lists/{list_id}/regenerate", json={
                "recipe_entries": recipe_entries or [],
                "exclude_long_term": exclude_long_term,
                "name": name or "",
                "extra_items": extra_items or [],
                "lt_missing": lt_missing or [],
            }, headers={"If-Match": f'"{etag}"'})
        r.raise_for_status()
        return r.json()["id"]

    def delete_list(self, list_id: str):
        """GET etag then DELETE /shopping-lists/{id}."""
        try:
            etag = self._get_etag(list_id)
            s = get_session()
            r = s.delete(
                f"{base_url()}/shopping-lists/{list_id}",
                headers={"If-Match": f'"{etag}"'},
            )
            if r.status_code == 412:
                etag = self._get_etag(list_id)
                r = s.delete(
                    f"{base_url()}/shopping-lists/{list_id}",
                    headers={"If-Match": f'"{etag}"'},
                )
            r.raise_for_status()
        except Exception:
            pass

    def mark_purchased(self, list_id: str, item_name: str, purchased: bool):
        """GET etag then PATCH /shopping-lists/{list_id}/items/{item_name}/purchased."""
        try:
            etag = self._get_etag(list_id)
            s = get_session()
            r = s.patch(
                f"{base_url()}/shopping-lists/{list_id}/items/{item_name}/purchased",
                params={"purchased": str(purchased).lower()},
                headers={"If-Match": f'"{etag}"'},
            )
            if r.status_code == 412:
                etag = self._get_etag(list_id)
                r = s.patch(
                    f"{base_url()}/shopping-lists/{list_id}/items/{item_name}/purchased",
                    params={"purchased": str(purchased).lower()},
                    headers={"If-Match": f'"{etag}"'},
                )
            r.raise_for_status()
        except Exception:
            pass

    def freeform_add_item(self, list_id: str, item_name: str) -> bool:
        """GET etag then POST /shopping-lists/{list_id}/items."""
        try:
            etag = self._get_etag(list_id)
            s = get_session()
            r = s.post(
                f"{base_url()}/shopping-lists/{list_id}/items",
                json={"item_name": item_name},
                headers={"If-Match": f'"{etag}"'},
            )
            if r.status_code == 412:
                etag = self._get_etag(list_id)
                r = s.post(
                    f"{base_url()}/shopping-lists/{list_id}/items",
                    json={"item_name": item_name},
                    headers={"If-Match": f'"{etag}"'},
                )
            r.raise_for_status()
            return True
        except Exception:
            return False

    def freeform_remove_item(self, list_id: str, item_name: str) -> bool:
        """GET etag then DELETE /shopping-lists/{list_id}/items/{item_name}."""
        try:
            etag = self._get_etag(list_id)
            s = get_session()
            r = s.delete(
                f"{base_url()}/shopping-lists/{list_id}/items/{item_name}",
                headers={"If-Match": f'"{etag}"'},
            )
            if r.status_code == 412:
                etag = self._get_etag(list_id)
                r = s.delete(
                    f"{base_url()}/shopping-lists/{list_id}/items/{item_name}",
                    headers={"If-Match": f'"{etag}"'},
                )
            r.raise_for_status()
            return True
        except Exception:
            return False

    def freeform_link_item(self, list_id: str, item_name: str, target_name: str | None = None) -> bool:
        """GET etag then POST /shopping-lists/{list_id}/items/{item_name}/link."""
        try:
            etag = self._get_etag(list_id)
            params = {}
            if target_name:
                params["target_name"] = target_name
            s = get_session()
            r = s.post(
                f"{base_url()}/shopping-lists/{list_id}/items/{item_name}/link",
                params=params,
                headers={"If-Match": f'"{etag}"'},
            )
            if r.status_code == 412:
                etag = self._get_etag(list_id)
                r = s.post(
                    f"{base_url()}/shopping-lists/{list_id}/items/{item_name}/link",
                    params=params,
                    headers={"If-Match": f'"{etag}"'},
                )
            r.raise_for_status()
            return True
        except Exception:
            return False

    def export_text(self, list_id: str) -> str:
        """GET list, then format same as local ShoppingList.export_text."""
        list_data = self.get_list(list_id)
        if not list_data:
            return ""

        lines = [
            f"Shopping List — {list_data.get('name', '')}",
            f"Generated: {list_data.get('date_generated', '')[:10]}",
            "=" * 40,
        ]

        grouped: dict[str, list] = {}
        for item in list_data.get("items", []):
            tag = (item.get("tags") or ["Other"])[0]
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
        return "\n".join(lines)

    # ── local computation (client-side, uses cached item/recipe data) ─ #

    def _build_item_row(self, item_name: str, item_client, units_needed: int = 1) -> dict:
        details = item_client.get_item_details(item_name)
        price = item_client.get_item_price(item_name)
        return {
            "item_name": item_name,
            "purchased": False,
            "tags": (details.get("tags") or []) if details else [],
            "units_needed": units_needed,
            "price": round(float(price) * units_needed, 2) if price else None,
        }

    def compute_items(
        self,
        recipe_entries: list,
        exclude_long_term: bool = True,
        extra_items: list = None,
    ) -> list:
        from kai.clients.recipe_client import RecipeClient
        from kai.clients.item_client import ItemClient
        r, i = RecipeClient(), ItemClient()
        long_term = set(i.get_long_term_items()) if exclude_long_term else set()
        seen: dict[str, dict] = {}
        for entry in (recipe_entries or []):
            for ing in r.get_scaled_ingredients(entry["recipe_name"], entry.get("multiplier", 1)):
                name = ing.get("item_name", "")
                if not name or name in seen or name in long_term:
                    continue
                seen[name] = self._build_item_row(name, i)
        for extra in (extra_items or []):
            name = extra.get("item_name", "")
            if not name or name in seen or name in long_term:
                continue
            seen[name] = self._build_item_row(name, i, extra.get("units", 1))
        return list(seen.values())

    def compute_long_term_items(
        self,
        recipe_entries: list,
        extra_items: list = None,
    ) -> list:
        from kai.clients.recipe_client import RecipeClient
        from kai.clients.item_client import ItemClient
        r, i = RecipeClient(), ItemClient()
        long_term = set(i.get_long_term_items())
        seen: dict[str, dict] = {}
        for entry in (recipe_entries or []):
            for ing in r.get_scaled_ingredients(entry["recipe_name"], entry.get("multiplier", 1)):
                name = ing.get("item_name", "")
                if not name or name in seen or name not in long_term:
                    continue
                seen[name] = self._build_item_row(name, i)
        for extra in (extra_items or []):
            name = extra.get("item_name", "")
            if not name or name in seen or name not in long_term:
                continue
            seen[name] = self._build_item_row(name, i, extra.get("units", 1))
        return list(seen.values())

    def compute_nominal_items(self, recipe_entries: list) -> list:
        from kai.clients.recipe_client import RecipeClient
        from kai.clients.item_client import ItemClient
        r, i = RecipeClient(), ItemClient()
        seen: dict[str, dict] = {}
        for entry in (recipe_entries or []):
            for ing in r.get_scaled_ingredients(entry["recipe_name"], 1):
                if not ing.get("nominal"):
                    continue
                name = ing.get("item_name", "")
                if not name or name in seen:
                    continue
                price = i.get_item_price(name)
                seen[name] = {
                    "item_name": name,
                    "units_needed": 1,
                    "price": round(float(price), 2) if price else None,
                }
        return list(seen.values())
