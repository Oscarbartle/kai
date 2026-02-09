from kai.ui.layouts.items_add import ItemsAdd
from kai.ui.layouts.tags import Tags
from kai.ui.layouts.items_viewer import ItemsViewer
from kai.ui.state import State

import sys
from PySide6.QtWidgets import QApplication, QWidget, QGridLayout, QMainWindow

class KaiUi(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Kai")
        self.resize(1000,600)

        self.add_layouts()
        self.add_widgets()
        self.stylesheet()
        
    def stylesheet(self):
        self.setStyleSheet("""        
            QWidget#items_add {
                background-color: #23272e;
                border-radius: 8px;
                border: 2px solid #444c56;
            }
            
            QWidget#items_existing {
                background-color: #23272e;
                border-radius: 8px;
                border: 2px solid #444c56;
            }
            
            QWidget#items_details {
                background-color: #23272e;
                border-radius: 8px;
                border: 2px solid #444c56;
            }
        """)
        
    def add_layouts(self):
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.grid_layout = QGridLayout(self.central_widget)
        self.grid_layout.setContentsMargins(5, 5, 5, 5)
        self.grid_layout.setSpacing(5)
        
        self.grid_layout.setColumnStretch(0, 1) 
        self.grid_layout.setColumnStretch(1, 2)
        
    def add_widgets(self):
        self.state = State()

        self.items_add = ItemsAdd(self.state)
        self.items_add.setObjectName("items_add")
        self.grid_layout.addWidget(self.items_add, 0, 0)
        
        self.items_existing = Tags(self.state)
        self.items_existing.setObjectName("items_existing")
        self.grid_layout.addWidget(self.items_existing, 1, 0)
        
        self.items_details = ItemsViewer(self.state)
        self.items_details.setObjectName("items_details")
        self.grid_layout.addWidget(self.items_details, 0, 1, 2, 1)

def run():
    app = QApplication(sys.argv)
    window = KaiUi()
    window.show()
    sys.exit(app.exec())