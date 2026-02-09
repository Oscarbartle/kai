from PySide6.QtCore import QObject, Signal

class State(QObject):
    new_items = Signal()

    def __init__(self):
        super().__init__()

    def items_updated(self):
        print("STATE: items changed")
        self.new_items.emit()
