import uuid
from datetime import datetime

from kai.core.io import IO
from kai.core import settings
from .woolworths_data import WoolworthsData

class Item:
    def __init__(self):
        self.io = IO(settings.data_dir() / "items.json")
        self._migrate()

    def _migrate(self):
        """Add missing fields to existing items"""
        data = self.io.all()
        changed = False
        for item_id, item_data in data.items():
            if "is_long_term" not in item_data:
                item_data["is_long_term"] = False
                changed = True
            if "date_updated" not in item_data:
                item_data["date_updated"] = item_data.get("date_added", datetime.now().isoformat())
                changed = True
        if changed:
            self.io.write(data)
        
    def _get_online_data(self, stock_code: int):
        woolworths_data = WoolworthsData(stock_code)
        return woolworths_data.get_data()
    
    def _name_exists(self, name: str):
        """Check if an item with this name already exists"""
        all_items = self.io.all()
        return any(data.get("name") == name for data in all_items.values())
    
    def _get_id_by_name(self, name: str):
        """Get item ID by name"""
        all_items = self.io.all()
        for item_id, data in all_items.items():
            if data.get("name") == name:
                return item_id
        return None
        
    def create(self, name: str, stock_code: int, tags: list = None):
        item_id = str(uuid.uuid4())
        
        if not self._name_exists(name):
            self.io.create(item_id, {}, overwrite=True)
            self.io.update(item_id, {
                "name": name,
                "stock_code": stock_code,
                "online_data": self._get_online_data(stock_code),
                "tags": tags,
                "is_long_term": False,
                "date_added": datetime.now().isoformat(),
                "date_updated": datetime.now().isoformat()
            })
            print(f"{name} has been added")
        else:
            print("Item already exists")

    def update(self, name: str, key: str, value):
        if key == "id":
            return print("You cannot edit the id")
        
        item_id = self._get_id_by_name(name)
        if item_id:
            self.io.update(item_id, {key: value})
        else:
            return print("Item does not exist please create it")
        
    def delete(self, name: str):
        item_id = self._get_id_by_name(name)
        if item_id:
            self.io.delete(item_id)
        else:
            print("Item does not exist")

    # ----- Queries ----- #

    def get_item_names(self):
        all_items = self.io.all()
        return [data["name"] for data in all_items.values()]
    
    def get_items(self):
        """Returns list of tuples: (item_name, item_id)"""
        all_items = self.io.all()
        return [(data["name"], item_id) for item_id, data in all_items.items()]
    
    def get_item_details(self, item_name):
        item_id = self._get_id_by_name(item_name)
        if item_id:
            return self.io.all()[item_id]
        return None
    
    def get_item_tags(self):
        tags = []
        all_items = self.io.all()
        
        for data in all_items.values():
            doc_tags = data.get("tags")
            if doc_tags:
                tags.extend(doc_tags)
            
        return list(set(tags))

    def get_long_term_items(self):
        all_items = self.io.all()
        return [data["name"] for data in all_items.values() if data.get("is_long_term")]

    def get_short_term_items(self):
        all_items = self.io.all()
        return [data["name"] for data in all_items.values() if not data.get("is_long_term")]

    def get_item_price(self, item_name: str, mode: str = None):
        """Get item price. mode: 'per_unit' or 'per_weight'. If None, uses setting."""
        if mode is None:
            from kai.core import settings as app_settings
            mode = app_settings.get("price_display_mode")

        details = self.get_item_details(item_name)
        if not details or not details.get("online_data"):
            return None

        if mode == "per_weight":
            unit_econ = details["online_data"].get("Unit Economics", {})
            cup_price = unit_econ.get("Price per Kg/Unit")
            measure = unit_econ.get("Measure", "")
            if cup_price is not None and measure:
                # cup_price is per-kg or per-unit from Woolworths
                # If measure is "100g", return as-is
                # If measure is "1kg", divide by 10 to get per-100g
                cup_price = float(cup_price)
                if "kg" in measure.lower():
                    return round(cup_price / 10, 2)
                elif "100g" in measure.lower():
                    return round(cup_price, 2)
                elif "100ml" in measure.lower():
                    return round(cup_price, 2)
                elif "l" in measure.lower() or "1l" in measure.lower():
                    return round(cup_price / 10, 2)
                else:
                    return round(cup_price, 2)
            # fallback to unit price if weight not available
        return details["online_data"]["Standard Pricing"].get("Current Price")

    def get_package_size(self, item_name: str):
        """Derive package size from Woolworths pricing data.

        Returns (size, unit_type) e.g. (400, "g") or (1000, "mL").
        unit_type is always a base unit: "g", "mL", or "ea".
        Returns (None, None) if data is insufficient.
        """
        details = self.get_item_details(item_name)
        if not details or not details.get("online_data"):
            return None, None

        sp = details["online_data"].get("Standard Pricing", {})
        ue = details["online_data"].get("Unit Economics", {})

        price = sp.get("Current Price")
        cup_price = ue.get("Price per Kg/Unit")
        measure = (ue.get("Measure") or "").strip().lower()
        avg_weight = ue.get("Avg Pack Weight")

        if not price or not cup_price or cup_price == 0:
            if avg_weight and avg_weight > 0:
                return round(avg_weight * 1000), "g"
            return None, None

        ratio = price / cup_price

        if "kg" in measure:
            return round(ratio * 1000), "g"
        elif "100g" in measure:
            return round(ratio * 100), "g"
        elif "100ml" in measure:
            return round(ratio * 100), "mL"
        elif "l" in measure:
            return round(ratio * 1000), "mL"
        elif avg_weight and avg_weight > 0:
            return round(avg_weight * 1000), "g"
        else:
            return 1, "ea"

    def refresh_online_data(self, item_name: str):
        """Re-fetch Woolworths data for an item and persist it."""
        item_id = self._get_id_by_name(item_name)
        if not item_id:
            return None
        doc = self.io.all()[item_id]
        new_data = self._get_online_data(doc["stock_code"])
        if new_data:
            self.io.update(item_id, {
                "online_data": new_data,
                "date_updated": datetime.now().isoformat(),
            })
        return new_data