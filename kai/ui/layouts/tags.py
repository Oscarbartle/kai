from kai.objects.item import Item
from ..widgets.separators import create_hline
from ..widgets.list_box import ListBox

from PySide6.QtWidgets import QLabel, QWidget, QVBoxLayout, QStyle, QStyleOption
from PySide6.QtGui import QPainter

class Tags(QWidget):
    def __init__(self, state):
        super().__init__()

        self.state = state

        self.layout = QVBoxLayout()
        self.layout.setContentsMargins(10, 10, 10, 10)  
        self.layout.setSpacing(10)                   
        self.setLayout(self.layout)

        self.create_widgets()
        self.add_layouts()
        
    def paintEvent(self, event):
        opt = QStyleOption()
        opt.initFrom(self)
        p = QPainter(self)
        self.style().drawPrimitive(QStyle.PE_Widget, opt, p, self)

    def create_widgets(self):
        self.tags_label = QLabel("<h3>Tags:</h3>")

        self.tags_list = ListBox(searchable=True)
        default = ["All"]
        default.extend(Item().get_item_tags())
        self.tags_list.add_items(default)

    def add_layouts(self):
        self.layout.addWidget(create_hline())
        self.layout.addWidget(self.tags_label)
        self.layout.addWidget(create_hline())
        self.layout.addWidget(self.tags_list)
