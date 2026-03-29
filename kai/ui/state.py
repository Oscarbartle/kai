from PySide6.QtCore import QObject, Signal

class State(QObject):
    new_items = Signal()
    new_recipes = Signal()
    new_shopping_list = Signal()
    tag_selected = Signal(str)
    price_mode_changed = Signal()

    def __init__(self):
        super().__init__()

    def items_updated(self):
        print("STATE: items changed")
        self.new_items.emit()

    def recipes_updated(self):
        print("STATE: recipes changed")
        self.new_recipes.emit()

    def shopping_list_updated(self):
        print("STATE: shopping list changed")
        self.new_shopping_list.emit()

    def select_tag(self, tag: str):
        print(f"STATE: tag selected: {tag}")
        self.tag_selected.emit(tag)
