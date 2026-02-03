from kai.objects.item import Item

class Processor():

    def create_item(self, name, unit, tags: list = None):
        item = Item(name)
        return item.create(unit, tags)
        
    def update_item(self, name, key, value):
        item = Item(name)
        return item.update(name, key, value)
    
    def delete_item(self, name):
        item = Item(name)
        return item.delete()