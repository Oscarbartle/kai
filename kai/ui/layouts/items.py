from kai.objects.item import Item
from ..widgets.separators import create_hline
from ..widgets.list_box import ListBox

from PySide6.QtWidgets import QLabel, QWidget, QPushButton, QVBoxLayout, QFormLayout, QLineEdit, QComboBox

class ItemsLayout(QWidget):
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

    def create_widgets(self):
        self.title_label = QLabel("<h3>Add Items:</h3>")

        self.item_name_label = QLabel("Name:")
        self.item_name = QLineEdit()
        
        self.item_stock_code_label = QLabel("Stock Code:")
        self.item_stock_code = QLineEdit()

        self.item_tags_label = QLabel("Tags:")
        self.item_tags = QLineEdit()

        self.button = QPushButton("Add Item")

        self.items_label = QLabel("<h3>Existing Items:</h3>")

        self.items_list = ListBox(searchable=True)
        self.items_list.add_items(Item().get_item_names())

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
        self.layout.addWidget(create_hline())
        self.layout.addWidget(self.items_label)
        self.layout.addWidget(create_hline())
        self.layout.addWidget(self.items_list)

    def connections(self):
        self.button.clicked.connect(self.on_add_item)

    def on_add_item(self):
        name = self.item_name.text()
        stock_code = self.item_stock_code.text()
        tags = self.item_tags.text().split(",")
        
        Item().create(name, stock_code, tags)
        self.items_list._refresh_list_display(Item().get_item_names())