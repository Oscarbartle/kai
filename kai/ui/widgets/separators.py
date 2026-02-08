from PySide6.QtWidgets import QFrame, QWidget

def create_hline():
    line = QWidget()
    line.setFixedHeight(2)
    line.setStyleSheet("background-color: #444c56; border-radius: 1px;")
    return line

def create_vline():
    line = QWidget()
    line.setFixedWidth(2)
    line.setStyleSheet("background-color: #444c56; border-radius: 1px;")
    return line