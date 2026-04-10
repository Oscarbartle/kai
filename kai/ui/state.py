from PySide6.QtCore import QObject, Signal, QTimer

class State(QObject):
    new_items = Signal()
    new_recipes = Signal()
    new_shopping_list = Signal()
    tag_selected = Signal(str)
    price_mode_changed = Signal()

    def __init__(self):
        super().__init__()
        # Debounce rapid back-to-back update signals so the UI only rebuilds once
        # per burst (e.g. items_updated + recipes_updated fired together after a
        # background refresh).
        self._items_timer = QTimer(self)
        self._items_timer.setSingleShot(True)
        self._items_timer.setInterval(80)
        self._items_timer.timeout.connect(self.new_items)

        self._recipes_timer = QTimer(self)
        self._recipes_timer.setSingleShot(True)
        self._recipes_timer.setInterval(80)
        self._recipes_timer.timeout.connect(self.new_recipes)

    def items_updated(self):
        self._items_timer.start()   # restarts if already counting → debounces burst

    def recipes_updated(self):
        self._recipes_timer.start()

    def shopping_list_updated(self):
        self.new_shopping_list.emit()

    def select_tag(self, tag: str):
        print(f"STATE: tag selected: {tag}")
        self.tag_selected.emit(tag)
