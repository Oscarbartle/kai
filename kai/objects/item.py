import os
import uuid
from datetime import datetime

from kai.core.io import IO
from .woolworths_data import WoolworthsData

class Item:
    def __init__(self, name):

        self.name = name

        json_path = os.path.join(os.path.dirname(__file__), "../../data/items.json")
        self.io = IO(json_path)
        
    def _get_online_data(self, stock_code: int):
        woolworths_data = WoolworthsData(stock_code)
        return woolworths_data.get_data()
        
    def create(self, unit: str, stock_code: int, tags: list = None):
        if not self.io.exists(self.name):
            self.io.create(self.name, {}, overwrite=True)
            self.io.update(self.name, {
                "id": str(uuid.uuid4()),
                "unit": unit,
                "online_data": self._get_online_data(stock_code),
                "tags": tags,
                "date_added": datetime.now().isoformat()
            })
            print(f"{self.name} has been added")
        else:
            print("Item already exists")

    def update(self, key: str, value):
        if key == "id":
            return print("You cannot edit the id")
        
        if self.io.exists(self.name):
            self.io.update(self.name, {key: value})
        else:
            return print("Item does not exist please create it")
        
    def delete(self):
        self.io.delete(self.name)