from kai.ui.layouts.items import ItemsLayout

import sys
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout

class KaiUi(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Kai")
        self.setGeometry(100, 100, 300, 200)

        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        self.add_widgets()

    def add_widgets(self):
        self.layout.addWidget(ItemsLayout())

def run():
    app = QApplication(sys.argv)
    window = KaiUi()
    window.show()
    sys.exit(app.exec())