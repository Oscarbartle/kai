from kai.objects.item import Item
from kai.utils.format_date import format_date

from PySide6.QtWidgets import QLabel, QWidget, QGridLayout, QStyle, QStyleOption, QHBoxLayout
from PySide6.QtGui import QPainter
from PySide6.QtCore import Qt

class ItemDetails(QWidget):
    def __init__(self, item_name):
        super().__init__()
        
        doc = Item().get_item_details(item_name)
        
        if doc is None:
            print(f"Item {item_name} not found")
            return
        
        self.name = doc["name"]
        self.id = self._get_id_by_name(item_name)
        
        self.stock_code = doc["stock_code"]
        
        self.current_price = float(doc["online_data"]["Standard Pricing"]["Current Price"])
        self.original_price = float(doc["online_data"]["Standard Pricing"]["Original Price"])
        
        if self.current_price < self.original_price:
            self.is_special = True
        else: 
            self.is_special = False
        
        self.discount_percentage = doc["online_data"]["Standard Pricing"]["Discount Percentage"]
        
        self.price_per_unit = float(doc["online_data"]["Unit Economics"]["Price per Kg/Unit"])
        self.measure = doc["online_data"]["Unit Economics"]["Measure"]
        
        self.total_savings = doc["online_data"]["Promotional Details"]["Total Savings"]
        self.promo_start = doc["online_data"]["Promotional Details"]["Promo Start"]
        self.promo_end = doc["online_data"]["Promotional Details"]["Promo End"]
        
        self.tags = doc["tags"]
        self.tags.sort()
        
        self.date_added = doc["date_added"]
        
        self.setObjectName("items_details")
        self.setMinimumHeight(60)
        self.setMaximumHeight(60)
        
        self.set_stylesheet()
        
        self.layouts()
        self.add_widgets()
        
        if self.is_special == True:
            self.add_layouts_special()
        else:
            self.add_layouts()
    
    def _get_id_by_name(self, name):
        """Helper to get ID from name"""
        return Item()._get_id_by_name(name)
        
    def set_stylesheet(self):
        self.setStyleSheet("""
            QWidget#items_details {
                background-color: #1D2026;
                border-radius: 8px;
                border: 2px solid #444c56;
            }
        """)
            
    def paintEvent(self, event):
        opt = QStyleOption()
        opt.initFrom(self)
        p = QPainter(self)
        self.style().drawPrimitive(QStyle.PE_Widget, opt, p, self)

    def layouts(self):
        self.grid_layout = QGridLayout()
        self.grid_layout.setContentsMargins(10, 6, 10, 6)
        self.grid_layout.setSpacing(5)
        self.setLayout(self.grid_layout)
        
        self.price_layout = QHBoxLayout()
        self.price_layout.setContentsMargins(0, 0, 0, 0)
        self.price_layout.setSpacing(8)

    def add_widgets(self):
        self.items_label = QLabel(f"<h3>{self.name}</h3>")
        self.tags_label = QLabel(f"<i>{", ".join(self.tags)}</i>")
        self.tags_label.setStyleSheet("color: #53616D; padding-left: 4px;")
        
        self.price_label = QLabel(f"<h3>${self.current_price}</h3>")
        self.price_label.setStyleSheet("color: #E6CB73;")
        
        self.measure_label = QLabel(f"<h4>${self.price_per_unit}/{self.measure}</h4>")
        self.measure_label.setStyleSheet("color: #7E93A6; padding-left: 4px;")
        
        self.date_added_label = QLabel(f"<h5>{format_date(self.date_added)}</h5>")
        self.date_added_label.setStyleSheet("color: #53616D;")
        self.date_added_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        self.stock_code_label = QLabel(f"<h5>{self.stock_code}</h5>")
        self.stock_code_label.setStyleSheet("color: #53616D;")
        self.stock_code_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        
        if self.is_special:
            self.original_price_label = QLabel(f"<h3>${self.original_price}</h3>")
            self.original_price_label.setStyleSheet("color: #FA5A59; text-decoration: line-through;")
            
            promo_start_text = format_date(self.promo_start) if self.promo_start else "N/A"
            promo_end_text = format_date(self.promo_end) if self.promo_end else "N/A"
            
            self.promo_start_label = QLabel(f"<h5>Start: {promo_start_text}</h5>")
            self.promo_start_label.setStyleSheet("color: #697A8A; padding-left: 15px;")
            
            self.promo_end_label = QLabel(f"<h5>End: {promo_end_text}</h5>")
            self.promo_end_label.setStyleSheet("color: #697A8A; padding-left: 15px;")

    def add_layouts(self):
        self.grid_layout.addWidget(self.items_label, 0, 0)
        self.grid_layout.addWidget(self.tags_label, 0, 1)
        
        self.grid_layout.setColumnStretch(1, 1)
        self.grid_layout.addWidget(self.stock_code_label, 0, 2)
        self.grid_layout.addWidget(self.date_added_label, 1, 2)

        self.grid_layout.addLayout(self.price_layout, 1, 0)
        self.price_layout.addWidget(self.price_label)
        self.price_layout.addStretch()
        self.grid_layout.addWidget(self.measure_label, 1, 1)
        
    def add_layouts_special(self):
        self.setStyleSheet("""
            QWidget#items_details {
                background-color: #1D2026;
                border-radius: 8px;
                border: 2px solid #5FB058;
            }
        """)
        self.price_label.setStyleSheet("color: #5FB058;")
        
        self.grid_layout.addWidget(self.items_label, 0, 0)
        self.grid_layout.addWidget(self.tags_label, 0, 2)
        
        self.grid_layout.addWidget(self.promo_start_label, 0, 3)
        self.grid_layout.addWidget(self.promo_end_label, 1, 3)
        
        self.grid_layout.setColumnStretch(3, 1)
        self.grid_layout.addWidget(self.stock_code_label, 0, 4)
        self.grid_layout.addWidget(self.date_added_label, 1, 4)

        self.grid_layout.addLayout(self.price_layout, 1, 0)
        self.price_layout.addWidget(self.price_label)
        self.price_layout.addWidget(self.original_price_label)
        self.price_layout.addStretch()
        self.grid_layout.addWidget(self.measure_label, 1, 2)