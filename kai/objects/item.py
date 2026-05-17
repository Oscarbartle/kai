import uuid
from datetime import datetime

from kai.core.io import IO
from kai.core import settings
from kai.utils.units import parse_woolworths_measure, derive_package_size
from .base_model import BaseModel
from .woolworths_data import WoolworthsData


class Item(BaseModel):
    """Pantry item model: CRUD, pricing, and Woolworths data refresh."""

    _migrated: set[str] = set()

    def __init__(self):
        self.io = IO(settings.data_dir() / "items.json")
        key = str(self.io.path)
        if key not in Item._migrated:
            self._migrate()
            Item._migrated.add(key)

    # ── migration ────────────────────────────────────────────────── #

    def _migrate(self):
        """Add missing fields to existing items (runs once per data file)."""
        data = self.io.all()
        changed = False
        for item_data in data.values():
            if "is_long_term" not in item_data:
                item_data["is_long_term"] = False
                changed = True
            if "date_updated" not in item_data:
                item_data["date_updated"] = item_data.get(
                    "date_added", datetime.now().isoformat()
                )
                changed = True
            if "sold_by_weight" not in item_data:
                item_data["sold_by_weight"] = False
                changed = True
            if "default_weight_kg" not in item_data:
                item_data["default_weight_kg"] = None
                changed = True
        if changed:
            self.io.write(data)

    # ── Woolworths data ──────────────────────────────────────────── #

    def _fetch_online_data(self, stock_code: int) -> dict | None:
        """Fetch Woolworths product data. Returns None if the request fails."""
        try:
            return WoolworthsData(stock_code).get_data()
        except RuntimeError:
            return None

    def refresh_online_data(self, item_name: str) -> dict | None:
        """Re-fetch Woolworths data for an item and persist it."""
        from .price_history import PriceHistory

        item_id = self._get_id_by_name(item_name)
        if not item_id:
            return None
        doc = self.io.all()[item_id]
        new_data = self._fetch_online_data(doc["stock_code"])
        if new_data is not None:
            out_of_stock = new_data.get("Availability", {}).get("Out of Stock", False)
            self.io.update(item_id, {
                "online_data": new_data,
                "date_updated": datetime.now().isoformat(),
                "unavailable": False,
                "out_of_stock": bool(out_of_stock),
            })
            sp = new_data.get("Standard Pricing", {})
            cur = sp.get("Current Price")
            orig = sp.get("Original Price")
            if cur is not None:
                PriceHistory().record(item_id, {
                    "current_price": float(cur),
                    "original_price": float(orig) if orig else None,
                    "on_special": bool(cur and orig and float(cur) < float(orig)),
                    "discount_pct": sp.get("Discount Percentage", ""),
                })
        else:
            self.io.update(item_id, {"unavailable": True, "out_of_stock": False})
        return new_data

    # ── CRUD ─────────────────────────────────────────────────────── #

    def create(
        self,
        name: str,
        stock_code: int,
        tags: list = None,
        sold_by_weight: bool = False,
        default_weight_kg: float | None = None,
    ) -> bool:
        """Create a new item.  Returns False if the name already exists."""
        return self._create_record(str(uuid.uuid4()), {
            "name": name,
            "stock_code": stock_code,
            "online_data": self._fetch_online_data(stock_code),
            "tags": tags,
            "is_long_term": False,
            "sold_by_weight": sold_by_weight,
            "default_weight_kg": default_weight_kg,
            "date_added": datetime.now().isoformat(),
            "date_updated": datetime.now().isoformat(),
        })

    def update(self, name: str, key: str, value) -> bool:
        """Update a single field on an existing item.  Returns False on error."""
        return self._update_record(name, key, value)

    def delete(self, name: str) -> bool:
        """Delete an item by name.  Returns False if not found."""
        return self._delete_record(name)

    # ── queries ──────────────────────────────────────────────────── #

    def get_item_names(self) -> list[str]:
        return self.get_names()

    def get_items(self) -> list[tuple[str, str]]:
        """Return list of (item_name, item_id) tuples."""
        return self.get_all()

    def get_item_details(self, item_name: str) -> dict | None:
        return self.get_details(item_name)

    def get_item_tags(self) -> list[str]:
        return self.get_tags()

    def get_long_term_items(self) -> list[str]:
        return [d["name"] for d in self.io.all().values() if d.get("is_long_term")]

    def get_short_term_items(self) -> list[str]:
        return [d["name"] for d in self.io.all().values() if not d.get("is_long_term")]

    # ── pricing ──────────────────────────────────────────────────── #

    def get_item_price(self, item_name: str, mode: str = None) -> float | None:
        """Return item price.  mode: ``'per_unit'`` or ``'per_weight'``.
        Falls back to the user setting when *mode* is None.
        """
        if mode is None:
            mode = settings.get("price_display_mode")

        details = self.get_item_details(item_name)
        if not details or not details.get("online_data"):
            return None

        online = details["online_data"]

        if mode == "per_weight":
            ue = online.get("Unit Economics", {})
            cup_price = ue.get("Price per Kg/Unit")
            measure = ue.get("Measure", "")
            per_weight = parse_woolworths_measure(float(cup_price), measure) if cup_price else None
            if per_weight is not None:
                return per_weight
            # fall through to unit price if weight data unavailable

        return online.get("Standard Pricing", {}).get("Current Price")

    def get_package_size(self, item_name: str) -> tuple[int | None, str | None]:
        """Derive package size from Woolworths pricing data.

        Returns ``(size, unit)`` e.g. ``(400, "g")`` or ``(1000, "mL")``.
        Returns ``(None, None)`` when data is insufficient.
        """
        details = self.get_item_details(item_name)
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