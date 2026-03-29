from kai.ui import theme

from PySide6.QtWidgets import QWidget

def create_hline():
    t = theme.theme()
    line = QWidget()
    line.setFixedHeight(1)
    line.setStyleSheet(f"background-color: {t.border}; border-radius: 0px;")
    return line

def create_vline():
    t = theme.theme()
    line = QWidget()
    line.setFixedWidth(1)
    line.setStyleSheet(f"background-color: {t.border}; border-radius: 0px;")
    return line