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

    # ── local computation stubs ───────────────────────────────────── #
    # The UI calls these on ShoppingList() instances in cart.py.
    # In remote mode, the generate endpoint handles this server-side.
    # The UI in cart.py calls sl.compute_items / compute_long_term_items
    # locally to build the preview — these are complex local computations
    # that require the local Item/Recipe objects. Raise NotImplementedError
    # so callers fall back or the UI can be updated to use generate instead.

    def compute_items(self, *args, **kwargs) -> list:
        raise NotImplementedError(
            "compute_items is not available in remote mode. "
            "Use ShoppingListClient.generate() instead."
        )

    def compute_long_term_items(self, *args, **kwargs) -> list:
        raise NotImplementedError(
            "compute_long_term_items is not available in remote mode. "
            "Use ShoppingListClient.generate() instead."
        )

    def compute_nominal_items(self, *args, **kwargs) -> list:
        raise NotImplementedError(
            "compute_nominal_items is not available in remote mode. "
            "Use ShoppingListClient.generate() instead."
        )
