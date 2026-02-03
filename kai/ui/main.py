from kai.ui.layouts.items import ItemsLayout

import sys
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QGridLayout, QMainWindow

class KaiUi(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Kai")
        self.resize(300,200)

        self.add_widgets()
        self.layout()
        self.stylesheet()
        
    def stylesheet(self):
        self.setStyleSheet(f"""        
            QWidget#items_layout {{
                background-color: #23272e;
                border-radius: 8px;
                border: 2px solid #444c56;
            }}
        """)
        
    def add_widgets(self):
        self.central_widget = QWidget()
        self.main_layout = QVBoxLayout(self.central_widget)
        self.grid_layout = QGridLayout()
        
        self.items_layout = ItemsLayout()
        self.setObjectName("items_layout") 
        
    def layout(self):
        self.setCentralWidget(self.central_widget)
        self.main_layout.setContentsMargins(5, 5, 5, 5)
        self.main_layout.setSpacing(5)
        self.main_layout.addWidget(self.items_layout)

def run():
    app = QApplication(sys.argv)
    window = KaiUi()
    window.show()
    sys.exit(app.exec())