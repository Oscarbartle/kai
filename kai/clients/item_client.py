"""HTTP client for the /items API endpoints."""
from __future__ import annotations

from kai.clients.http import get_session, base_url


class ItemClient:
    def __init__(self):
        self._cache: dict | None = None
        self.io = self._IoProxy(self)

    # ── cache ─────────────────────────────────────────────────────── #

    def _fetch_all(self) -> dict:
        """GET /items and return {id: item_dict} (etag stripped from values)."""
        s = get_session()
        r = s.get(f"{base_url()}/items")
        r.raise_for_status()
        result = {}
        for item in r.json():
            iid = item["id"]
            doc = {k: v for k, v in item.items() if k not in ("id", "etag")}
            result[iid] = doc
        return result

    def _get_cache(self) -> dict:
        if self._cache is None:
            self._cache = self._fetch_all()
        return self._cache

    def _invalidate(self):
        self._cache = None

    # ── _IoProxy ─────────────────────────────────────────────────── #

    class _IoProxy:
        def __init__(self, client: "ItemClient"):
            self._client = client

        def all(self) -> dict:
            return self._client._get_cache()

    # ── lookup helpers ────────────────────────────────────────────── #

    def _get_id_by_name(self, name: str) -> str | None:
        for iid, doc in self._get_cache().items():
            if doc.get("name") == name:
                return iid
        return None

    def _get_etag(self, item_id: str) -> str:
        s = get_session()
        r = s.get(f"{base_url()}/items/{item_id}")
        r.raise_for_status()
        return r.json().get("etag", "")

    # ── query API ─────────────────────────────────────────────────── #

    def get_item_names(self) -> list[str]:
        return [doc["name"] for doc in self._get_cache().values() if doc.get("name")]

    def get_items(self) -> list[tuple[str, str]]:
        """Return (name, id) tuples."""
        return [(doc["name"], iid) for iid, doc in self._get_cache().items() if doc.get("name")]

    def get_item_details(self, name: str) -> dict | None:
        iid = self._get_id_by_name(name)
        if iid is None:
            return None
        return self._get_cache().get(iid)

    def get_item_tags(self) -> list[str]:
        tags: set[str] = set()
        for doc in self._get_cache().values():
            for tag in (doc.get("tags") or []):
                tags.add(tag)
        return sorted(tags)

    def get_long_term_items(self) -> list[str]:
        return [doc["name"] for doc in self._get_cache().values() if doc.get("is_long_term")]

    def get_short_term_items(self) -> list[str]:
        return [doc["name"] for doc in self._get_cache().values() if not doc.get("is_long_term")]

    def get_item_price(self, name: str, mode: str = None) -> float | None:
        """Return item price. Falls back to user setting when mode is None."""
        if mode is None:
            from kai.core import settings
            mode = settings.get("price_display_mode")

        details = self.get_item_details(name)
        if not details or not details.get("online_data"):
            return None

        online = details["online_data"]

        if mode == "per_weight":
            from kai.utils.units import parse_woolworths_measure
            ue = online.get("Unit Economics", {})
            cup_price = ue.get("Price per Kg/Unit")
            measure = ue.get("Measure", "")
            per_weight = parse_woolworths_measure(float(cup_price), measure) if cup_price else None
            if per_weight is not None:
                return per_weight
            # fall through to unit price if weight data unavailable

        return online.get("Standard Pricing", {}).get("Current Price")

    def get_package_size(self, name: str) -> tuple:
        """Derive package size from Woolworths pricing data.

        Returns (size, unit) e.g. (400, "g") or (1000, "mL").
        Returns (None, None) when data is insufficient.
        """
        from kai.utils.units import derive_package_size
        details = self.get_item_details(name)
        if not details or not details.get("online_data"):
            return None, None

        online = details["online_data"]
        sp = online.get("Standard Pricing", {})
        ue = online.get("Unit Economics", {})

        return derive_package_size(
            price=sp.get("Current Price"),
            cup_price=ue.get("Price per Kg/Unit"),
            measure=ue.get("Measure", ""),
            avg_weight=ue.get("Avg Pack Weight"),
        )

    # ── mutation API ──────────────────────────────────────────────── #

    def refresh_online_data(self, name: str) -> dict | None:
        """POST /items/{id}/refresh and return online_data from response."""
        try:
            iid = self._get_id_by_name(name)
            if iid is None:
                return None
            s = get_session()
            r = s.post(f"{base_url()}/items/{iid}/refresh")
            r.raise_for_status()
            self._invalidate()
            data = r.json()
            return data.get("online_data")
        except Exception:
            return None

    def create(
        self,
        name: str,
        stock_code,
        tags: list,
        sold_by_weight: bool = False,
        default_weight_kg: float | None = None,
    ) -> bool:
        try:
            s = get_session()
            r = s.post(f"{base_url()}/items", json={
                "name": name,
                "stock_code": stock_code,
                "tags": tags or [],
                "sold_by_weight": sold_by_weight,
                "default_weight_kg": default_weight_kg,
            })
            r.raise_for_status()
            self._invalidate()
            return True
        except Exception:
            return False

    def update(self, name: str, key: str, value) -> bool:
        try:
            iid = self._get_id_by_name(name)
            if iid is None:
                return False
            etag = self._get_etag(iid)
            s = get_session()
            r = s.put(
                f"{base_url()}/items/{iid}",
                json={key: value},
                headers={"If-Match": f'"{etag}"'},
            )
            if r.status_code == 412:
                etag = self._get_etag(iid)
                r = s.put(
                    f"{base_url()}/items/{iid}",
                    json={key: value},
                    headers={"If-Match": f'"{etag}"'},
                )
            r.raise_for_status()
            self._invalidate()
            return True
        except Exception:
            return False

    def delete(self, name: str) -> bool:
        try:
            iid = self._get_id_by_name(name)
            if iid is None:
                return False
            etag = self._get_etag(iid)
            s = get_session()
            r = s.delete(
                f"{base_url()}/items/{iid}",
                headers={"If-Match": f'"{etag}"'},
            )
            if r.status_code == 412:
                etag = self._get_etag(iid)
                r = s.delete(
                    f"{base_url()}/items/{iid}",
                    headers={"If-Match": f'"{etag}"'},
                )
            r.raise_for_status()
            self._invalidate()
            return True
        except Exception:
            return False
