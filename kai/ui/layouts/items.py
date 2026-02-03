from kai.objects.item import Item
from ..widgets.separators import create_hline

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
        self.label = QLabel("<h3>Items:</h3>")

        self.item_name_label = QLabel("Name:")
        self.item_name = QLineEdit()
        
        self.item_unit_label = QLabel("Unit:")
        self.item_unit = QComboBox()
        self.item_unit.addItems(["Quantity", "Grams", "Kilograms", "Liters", "Milliliters"])
        
        self.item_stock_code_label = QLabel("Stock Code:")
        self.item_stock_code = QLineEdit()

        self.item_tags_label = QLabel("Tags:")
        self.item_tags = QLineEdit()

        self.button = QPushButton("Add Item")

    def create_layouts(self):
        self.form_layout = QFormLayout()
        self.form_layout.addRow(self.item_name_label, self.item_name)
        self.form_layout.addRow(self.item_unit_label, self.item_unit)
        self.form_layout.addRow(self.item_stock_code_label, self.item_stock_code)
        self.form_layout.addRow(self.item_tags_label, self.item_tags)

    def add_layouts(self):
        self.layout.addWidget(self.label)
        self.layout.addWidget(create_hline())
        self.layout.addLayout(self.form_layout)
        self.layout.addWidget(self.button)

    def connections(self):
        self.button.clicked.connect(self.on_button_click)

    def on_button_click(self):
        name = self.item_name.text()
        unit = self.item_unit.currentText()
        stock_code = self.item_stock_code.text()
        tags = self.item_tags.text().split(",")
        
        item = Item(name)
        item.create(unit, stock_code, tags)