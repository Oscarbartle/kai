from kai.objects.item import Item
from ..widgets.separators import create_hline

from PySide6.QtWidgets import QWidget, QStyle, QStyleOption, QPushButton, QVBoxLayout, QFormLayout, QLineEdit, QLabel
from PySide6.QtGui import QPainter

class ItemsAdd(QWidget):
    def __init__(self):
        super().__init__()

        self.layout = QVBoxLayout()
        self.layout.setContentsMargins(10, 10, 10, 10)  
        self.layout.setSpacing(10)                   
        self.setLayout(self.layout)

        self.create_widgets()
        self.create_layouts()
        self.add_layouts()
        self.connections()

    def paintEvent(self, event):
        opt = QStyleOption()
        opt.initFrom(self)
        p = QPainter(self)
        self.style().drawPrimitive(QStyle.PE_Widget, opt, p, self)

    def create_widgets(self):
        self.title_label = QLabel("<h3>Add Items:</h3>")

        self.item_name_label = QLabel("Name:")
        self.item_name = QLineEdit()
        
        self.item_stock_code_label = QLabel("Stock Code:")
        self.item_stock_code = QLineEdit()

        self.item_tags_label = QLabel("Tags:")
        self.item_tags = QLineEdit()

        self.button = QPushButton("Add Item")

    def create_layouts(self):
        self.form_layout = QFormLayout()
        self.form_layout.addRow(self.item_name_label, self.item_name)
        self.form_layout.addRow(self.item_stock_code_label, self.item_stock_code)
        self.form_layout.addRow(self.item_tags_label, self.item_tags)

    def add_layouts(self):
        self.layout.addWidget(create_hline())
        self.layout.addWidget(self.title_label)
        self.layout.addWidget(create_hline())
        self.layout.addLayout(self.form_layout)
        self.layout.addWidget(self.button)

    def connections(self):
        self.button.clicked.connect(self.on_add_item)

    def on_add_item(self):
        name = self.item_name.text()
        stock_code = self.item_stock_code.text()
        tags = self.item_tags.text().split(",")
        
        Item().create(name, stock_code, tags)
        
        self.item_name.clear()
        self.item_stock_code.clear()
        self.item_tags.clear()