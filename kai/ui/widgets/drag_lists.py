from PySide6.QtWidgets import QListWidget, QAbstractItemView
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtCore import Qt, QMimeData


class DragSourceList(QListWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragEnabled(True)
        self.setDefaultDropAction(Qt.DropAction.CopyAction)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)

    def mimeData(self, items):
        mime = QMimeData()
        names = "\n".join(item.text() for item in items)
        mime.setText(names)
        return mime


class DropTargetList(QListWidget):
    def __init__(self, on_drop_callback=None, parent=None):
        super().__init__(parent)
        self.on_drop_callback = on_drop_callback
        self.setAcceptDrops(True)
        self.setDragEnabled(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasText():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if event.mimeData().hasText():
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event: QDropEvent):
        if event.source() == self:
            super().dropEvent(event)
            return
        if event.mimeData().hasText():
            names = event.mimeData().text().strip().split("\n")
            if self.on_drop_callback:
                self.on_drop_callback(names)
            event.acceptProposedAction()
