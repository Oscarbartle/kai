from kai.handlers.processor import Processor

from PySide6.QtWidgets import QLabel, QWidget, QPushButton, QVBoxLayout, QHBoxLayout, QLineEdit, QComboBox

class ItemsLayout(QWidget):
    def __init__(self):
        super().__init__()

        self.processor = Processor()

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
        self.item_unit.addItems(["Grams", "Kilograms", "Liters", "Milliliters"])

        self.item_tags_label = QLabel("Tags:")
        self.item_tags = QLineEdit()

        self.button = QPushButton("Add Item")

    def create_layouts(self):
        self.name_row = QHBoxLayout()
        self.name_row.addWidget(self.item_name_label)
        self.name_row.addWidget(self.item_name)

        self.unit_row = QHBoxLayout()
        self.unit_row.addWidget(self.item_unit_label)
        self.unit_row.addWidget(self.item_unit)

        self.tags_row = QHBoxLayout()
        self.tags_row.addWidget(self.item_tags_label)
        self.tags_row.addWidget(self.item_tags)

    def add_layouts(self):
        self.layout.addWidget(self.label)
        self.layout.addLayout(self.name_row)
        self.layout.addLayout(self.unit_row)
        self.layout.addLayout(self.tags_row)
        self.layout.addWidget(self.button)

    def connections(self):
        self.button.clicked.connect(self.on_button_click)

    def on_button_click(self):
        name = self.item_name.text()
        unit = self.item_unit.currentText()
        tags = self.item_tags.text().split(",")

        self.processor.create_item(name, unit, tags)


