from kai.ui.layouts.items.page import ItemsPage
from kai.ui.layouts.recipes.page import RecipesPage
from kai.ui.layouts.shopping_list.page import ShoppingListPage
from kai.ui.layouts.settings.page import SettingsPage
from kai.ui.layouts.stats.page import StatsPage
from kai.ui.widgets.nav_button import NavButton, _colorize_svg
from kai.ui.state import State
from kai.ui import theme
from kai.ui.tokens import SPACE_SM, SPACE_MD, SPACE_LG, FS_META, FW_MEDIUM, RADIUS_SM, H_ICON_BTN

import sys
from PySide6.QtWidgets import (
    QApplication, QWidget, QHBoxLayout, QVBoxLayout,
    QMainWindow, QStackedWidget, QButtonGroup, QLabel, QComboBox, QPushButton,
    QProgressBar,
)
from PySide6.QtGui import QPixmap
from PySide6.QtCore import Qt, QSize
from pathlib import Path

_ICONS = Path(__file__).resolve().parent.parent / "icons"

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
        self._wire_progress()

    def apply_theme(self):
        self.setStyleSheet(theme.global_stylesheet())

    def add_layouts(self):
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)

        # Outer vertical layout: content row on top, progress bar pinned to bottom
        outer = QVBoxLayout(self.central_widget)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        content_row = QWidget()
        self.main_layout = QHBoxLayout(content_row)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        outer.addWidget(content_row, 1)

        # ----- sidebar ----- #
        self.sidebar = QWidget()
        self.sidebar.setObjectName("sidebar")
        self.sidebar.setFixedWidth(180)
        self.sidebar_layout = QVBoxLayout(self.sidebar)
        self.sidebar_layout.setContentsMargins(10, 20, 10, 20)
        self.sidebar_layout.setSpacing(6)

        # ----- pages stack ----- #
        self.stack = QStackedWidget()

        self.main_layout.addWidget(self.sidebar)
        self.main_layout.addWidget(self.stack, 1)

        # ----- progress bar ----- #
        t = theme.theme()
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(3)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{
                background: transparent;
                border: none;
            }}
            QProgressBar::chunk {{
                background: {t.accent};
                border-radius: 1px;
            }}
        """)
        self.progress_bar.hide()
        outer.addWidget(self.progress_bar)

    def add_nav(self):
        # app logo
        logo_path = Path(__file__).resolve().parent.parent / "icons" / "logo.png"
        logo_label = QLabel()
        pixmap = QPixmap(str(logo_path))
        dpr = self.screen().devicePixelRatio() if self.screen() else 1
        scaled = pixmap.scaledToWidth(int(80 * dpr), Qt.TransformationMode.SmoothTransformation)
        scaled.setDevicePixelRatio(dpr)
        logo_label.setPixmap(scaled)
        logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo_label.setStyleSheet("padding-top: 5px 0; padding-bottom: 15px 0;")

        self.sidebar_layout.addWidget(logo_label)
 
        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)

        nav_items = [
            ("Items",         str(_ICONS / "items.svg")),
            ("Recipes",       str(_ICONS / "recipes.svg")),
            ("Shopping List", str(_ICONS / "shopping.svg")),
            ("Insights",      str(_ICONS / "star.svg")),
        ]
        self.nav_buttons = []

        for i, (label, icon_path) in enumerate(nav_items):
            btn = NavButton(label, icon_path=icon_path)
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

        # settings button at the bottom
        self.settings_gear_btn = NavButton("Settings", icon_path=str(_ICONS / "settings.svg"))
        self.settings_gear_btn.setFixedHeight(42)
        self.nav_group.addButton(self.settings_gear_btn, 4)
        self.sidebar_layout.addSpacing(SPACE_SM)
        self.sidebar_layout.addWidget(self.settings_gear_btn)

        self.nav_group.idClicked.connect(self._on_nav_clicked)
        self.nav_buttons[0].setChecked(True)
        self.settings_gear_btn.setStyleSheet(self.settings_gear_btn._build_style())

    def _on_nav_clicked(self, idx: int):
        self.stack.setCurrentIndex(idx)
        self._refresh_nav_icons()

    def _refresh_nav_icons(self):
        all_btns = self.nav_buttons + [self.settings_gear_btn]
        for btn in all_btns:
            btn._refresh_icon()

    def _on_theme_changed(self, name: str):
        theme.set_theme(name.lower())
        self.apply_theme()
        all_btns = self.nav_buttons + [self.settings_gear_btn]
        for btn in all_btns:
            btn.setStyleSheet(btn._build_style())
            btn._refresh_icon()
        if hasattr(self, "settings_page"):
            self.settings_page.refresh_base_combo()

    def _on_settings_theme_changed(self):
        self.apply_theme()
        all_btns = self.nav_buttons + [self.settings_gear_btn]
        for btn in all_btns:
            btn.setStyleSheet(btn._build_style())
            btn._refresh_icon()
        # rebuild theme combo
        self.theme_combo.blockSignals(True)
        self.theme_combo.clear()
        self.theme_combo.addItems([n.capitalize() for n in theme.theme_names()])
        self.theme_combo.setCurrentText(theme.theme().name.capitalize())
        self.theme_combo.blockSignals(False)
        self.settings_page.refresh_base_combo()

    def _wire_progress(self):
        from kai.ui import refresh_worker
        refresh_worker.progress.started.connect(self._on_refresh_started)
        refresh_worker.progress.step.connect(self._on_refresh_step)
        refresh_worker.progress.finished.connect(self._on_refresh_finished)

    def _on_refresh_started(self, total: int):
        self.progress_bar.setRange(0, total)
        self.progress_bar.setValue(0)
        self.progress_bar.show()

    def _on_refresh_step(self, done: int, total: int):
        self.progress_bar.setRange(0, total)
        self.progress_bar.setValue(done)

    def _on_refresh_finished(self):
        self.progress_bar.setValue(self.progress_bar.maximum())
        # Brief pause so user sees 100% before it disappears
        from PySide6.QtCore import QTimer
        QTimer.singleShot(600, self.progress_bar.hide)

    def _on_price_mode_changed(self):
        self.state.price_mode_changed.emit()

    def add_pages(self):
        self.items_page = ItemsPage(self.state)
        self.stack.addWidget(self.items_page)

        self.recipes_page = RecipesPage(self.state)
        self.stack.addWidget(self.recipes_page)

        self.shopping_list_page = ShoppingListPage(self.state)
        self.stack.addWidget(self.shopping_list_page)

        self.insights_page = StatsPage(self.state)
        self.stack.addWidget(self.insights_page)

        self.settings_page = SettingsPage()
        self.settings_page.theme_changed.connect(self._on_settings_theme_changed)
        self.settings_page.price_mode_changed.connect(self._on_price_mode_changed)
        self.stack.addWidget(self.settings_page)

def run():
    app = QApplication(sys.argv)
    window = KaiUi()
    window.show()
    sys.exit(app.exec())