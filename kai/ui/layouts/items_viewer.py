from kai.objects.item import Item
from ..widgets.item_details import ItemDetails
from ..widgets.separators import create_hline

from PySide6.QtWidgets import QLabel, QWidget, QVBoxLayout, QStyle, QStyleOption, QScrollArea
from PySide6.QtGui import QPainter


class ItemsViewer(QWidget):
    def __init__(self):
        super().__init__()

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
        self.items_label = QLabel("<h3>Items Viewer:</h3>")
        
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("""
            QScrollArea {
                background: transparent;
                border: none;
            }
            QScrollBar:vertical {
                background: transparent;
                width: 4px;
                border-radius: 2px;
                border: none;
            }
            QScrollBar::handle:vertical {
                background: #8b949e;
                border-radius: 2px;
            }
            QScrollBar::handle:vertical:hover {
                background: #BFCBD9;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)
        
        self.scroll_widget = QWidget()
        self.scroll_widget.setStyleSheet("background: transparent;")
        self.scroll_layout = QVBoxLayout(self.scroll_widget)
        self.scroll_layout.setContentsMargins(2, 2, 2, 2)
        self.scroll_layout.setSpacing(5)
        
        items_data = Item().get_items()
        items_data.sort(key=lambda x: x[0])
        
        for name, item_id in items_data:
            self.scroll_layout.addWidget(ItemDetails(name))

        self.scroll_layout.addStretch()
        
        self.scroll_area.setWidget(self.scroll_widget)

    def add_layouts(self):
        self.layout.addWidget(create_hline())
        self.layout.addWidget(self.items_label)
        self.layout.addWidget(create_hline())
        self.layout.addWidget(self.scroll_area)