import os
import uuid
from datetime import datetime

from kai.core.io import IO
from .woolworths_data import WoolworthsData

class Item:
    def __init__(self):
        json_path = os.path.join(os.path.dirname(__file__), "../../data/items.json")
        self.io = IO(json_path)
        
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
                "date_added": datetime.now().isoformat()
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