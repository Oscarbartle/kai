from kai.ui.layouts.items_page import ItemsPage
from kai.ui.layouts.recipes_page import RecipesPage
from kai.ui.layouts.shopping_list_page import ShoppingListPage
from kai.ui.layouts.settings_page import SettingsPage
from kai.ui.widgets.nav_button import NavButton
from kai.ui.state import State
from kai.ui import theme

import sys
from PySide6.QtWidgets import (
    QApplication, QWidget, QHBoxLayout, QVBoxLayout,
    QMainWindow, QStackedWidget, QButtonGroup, QLabel, QComboBox
)
from PySide6.QtGui import QPixmap, QColor
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGraphicsColorizeEffect
from pathlib import Path

class KaiUi(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Kai")
        self.resize(1200, 700)

        self.state = State()

        self.apply_theme()
        self.add_layouts()
        self.add_nav()
        self.add_pages()

    def apply_theme(self):
        self.setStyleSheet(theme.global_stylesheet())

    def add_layouts(self):
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)

        self.main_layout = QHBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # ----- sidebar ----- #
        self.sidebar = QWidget()
        self.sidebar.setObjectName("sidebar")
        self.sidebar.setFixedWidth(180)
        self.sidebar_layout = QVBoxLayout(self.sidebar)
        self.sidebar_layout.setContentsMargins(10, 16, 10, 16)
        self.sidebar_layout.setSpacing(4)

        # ----- pages stack ----- #
        self.stack = QStackedWidget()

        self.main_layout.addWidget(self.sidebar)
        self.main_layout.addWidget(self.stack, 1)

    def add_nav(self):
        # app logo
        logo_path = Path(__file__).resolve().parent.parent / "icons" / "logo.png"
        logo_label = QLabel()
        pixmap = QPixmap(str(logo_path))
        dpr = self.screen().devicePixelRatio() if self.screen() else 1
        scaled = pixmap.scaledToWidth(int(100 * dpr), Qt.TransformationMode.SmoothTransformation)
        scaled.setDevicePixelRatio(dpr)
        logo_label.setPixmap(scaled)
        logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo_label.setStyleSheet("padding-bottom: 15px 0;")

        self.sidebar_layout.addWidget(logo_label)
 
        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)

        nav_items = ["Items", "Recipes", "Shopping List", "Settings"]
        self.nav_buttons = []

        for i, label in enumerate(nav_items):
            btn = NavButton(label)
            self.nav_group.addButton(btn, i)
            self.sidebar_layout.addWidget(btn)
            self.nav_buttons.append(btn)

        self.sidebar_layout.addStretch()

        # theme picker
        theme_label = QLabel("Theme")
        theme_label.setProperty("role", "dim")
        self.sidebar_layout.addWidget(theme_label)

        self.theme_combo = QComboBox()
        self.theme_combo.addItems([n.capitalize() for n in theme.theme_names()])
        self.theme_combo.setCurrentText(theme.theme().name.capitalize())
        self.theme_combo.currentTextChanged.connect(self._on_theme_changed)
        self.sidebar_layout.addWidget(self.theme_combo)

        self.nav_group.idClicked.connect(self.stack.setCurrentIndex)
        self.nav_buttons[0].setChecked(True)

    def _on_theme_changed(self, name: str):
        theme.set_theme(name.lower())
        self.apply_theme()
        for btn in self.nav_buttons:
            btn.setStyleSheet(btn._build_style())
        if hasattr(self, "settings_page"):
            self.settings_page.refresh_base_combo()

    def _on_settings_theme_changed(self):
        self.apply_theme()
        for btn in self.nav_buttons:
            btn.setStyleSheet(btn._build_style())
        # rebuild theme combo
        self.theme_combo.blockSignals(True)
        self.theme_combo.clear()
        self.theme_combo.addItems([n.capitalize() for n in theme.theme_names()])
        self.theme_combo.setCurrentText(theme.theme().name.capitalize())
        self.theme_combo.blockSignals(False)
        self.settings_page.refresh_base_combo()

    def _on_price_mode_changed(self):
        self.state.price_mode_changed.emit()

    def add_pages(self):
        self.items_page = ItemsPage(self.state)
        self.stack.addWidget(self.items_page)

        self.recipes_page = RecipesPage(self.state)
        self.stack.addWidget(self.recipes_page)

        self.shopping_list_page = ShoppingListPage(self.state)
        self.stack.addWidget(self.shopping_list_page)

        self.settings_page = SettingsPage()
        self.settings_page.theme_changed.connect(self._on_settings_theme_changed)
        self.settings_page.price_mode_changed.connect(self._on_price_mode_changed)
        self.stack.addWidget(self.settings_page)

def run():
    app = QApplication(sys.argv)
    window = KaiUi()
    window.show()
    sys.exit(app.exec())