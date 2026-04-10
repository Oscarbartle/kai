from kai.ui import theme
from kai.core import settings as app_settings
from kai.ui.layouts.settings.theme_editor import ThemeEditor

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QComboBox,
    QMessageBox, QFileDialog, QFrame,
)
from PySide6.QtCore import Qt, Signal


class SettingsPage(QWidget):
    theme_changed = Signal()
    price_mode_changed = Signal()
    data_dir_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build()

    def _build(self):
        t = theme.theme()
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 18)
        root.setSpacing(12)

        def _card():
            w = QWidget()
            w.setObjectName("settings_card")
            w.setStyleSheet(theme.inline_card_css("settings_card"))
            lay = QVBoxLayout(w)
            lay.setContentsMargins(16, 16, 16, 16)
            lay.setSpacing(12)
            return w, lay

        def _slbl(text):
            lbl = QLabel(text)
            lbl.setStyleSheet(theme.section_label_css())
            return lbl

        def _divider():
            line = QFrame()
            line.setFrameShape(QFrame.Shape.HLine)
            line.setStyleSheet(theme.divider_line_css())
            return line

        # ── Card 1: General ───────────────────────────────────── #
        gen_card, gen_lay = _card()
        gen_lay.addWidget(_slbl("General"))

        price_lbl = QLabel("Show prices as")
        price_lbl.setProperty("role", "dim")
        gen_lay.addWidget(price_lbl)
        self.price_mode_combo = QComboBox()
        self.price_mode_combo.addItems(["Per Unit", "Per 100g"])
        current = app_settings.get("price_display_mode")
        self.price_mode_combo.setCurrentText(
            "Per 100g" if current == "per_weight" else "Per Unit"
        )
        self.price_mode_combo.setFixedHeight(34)
        self.price_mode_combo.currentTextChanged.connect(self._on_price_mode_changed)
        gen_lay.addWidget(self.price_mode_combo)

        gen_lay.addWidget(_divider())
        gen_lay.addWidget(_slbl("Supermarket Browser"))

        browser_lbl = QLabel("Browser used to add items to the Woolworths cart")
        browser_lbl.setProperty("role", "dim")
        browser_lbl.setWordWrap(True)
        gen_lay.addWidget(browser_lbl)
        self.browser_combo = QComboBox()
        self._browser_options = [
            ("Zen", "zen"),
            ("Firefox", "firefox"),
            ("Chrome", "chrome"),
            ("Brave", "brave"),
            ("Edge", "edge"),
            ("Chromium", "chromium"),
        ]
        for label, _ in self._browser_options:
            self.browser_combo.addItem(label)
        current_browser = app_settings.get("browser") or "firefox"
        for i, (_, key) in enumerate(self._browser_options):
            if key == current_browser:
                self.browser_combo.setCurrentIndex(i)
                break
        self.browser_combo.setFixedHeight(34)
        self.browser_combo.currentIndexChanged.connect(self._on_browser_changed)
        gen_lay.addWidget(self.browser_combo)

        gen_lay.addWidget(_divider())
        gen_lay.addWidget(_slbl("Data Folder"))

        dir_lbl = QLabel("Location")
        dir_lbl.setProperty("role", "dim")
        gen_lay.addWidget(dir_lbl)
        data_row = QHBoxLayout()
        data_row.setSpacing(8)
        self.data_dir_input = QLineEdit()
        self.data_dir_input.setPlaceholderText("Default (local data/ folder)")
        self.data_dir_input.setFixedHeight(34)
        current_dir = app_settings.get("data_dir") or ""
        self.data_dir_input.setText(current_dir)
        browse_btn = QPushButton("Browse…")
        browse_btn.setProperty("btn", "secondary")
        browse_btn.setFixedHeight(34)
        browse_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        browse_btn.clicked.connect(self._browse_data_dir)
        apply_dir_btn = QPushButton("Apply")
        apply_dir_btn.setProperty("btn", "primary")
        apply_dir_btn.setFixedHeight(34)
        apply_dir_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        apply_dir_btn.clicked.connect(self._apply_data_dir)
        data_row.addWidget(self.data_dir_input, 1)
        data_row.addWidget(browse_btn)
        data_row.addWidget(apply_dir_btn)
        gen_lay.addLayout(data_row)
        self.data_dir_status = QLabel("")
        self.data_dir_status.setProperty("role", "dim")
        gen_lay.addWidget(self.data_dir_status)
        root.addWidget(gen_card)

        # ── Card 2: Theme Editor (extracted) ─────────────────── #
        theme_card, theme_lay = _card()
        self.theme_editor = ThemeEditor(self)
        self.theme_editor.theme_changed.connect(self.theme_changed.emit)
        theme_lay.addWidget(self.theme_editor)
        root.addWidget(theme_card, 1)

    # ── helpers ────────────────────────────────────────────────────── #
    def refresh_base_combo(self):
        self.theme_editor.refresh_base_combo()

    def _on_price_mode_changed(self, text: str):
        mode = "per_weight" if text == "Per 100g" else "per_unit"
        app_settings.set("price_display_mode", mode)
        self.price_mode_changed.emit()

    def _on_browser_changed(self, index: int):
        _, key = self._browser_options[index]
        app_settings.set("browser", key)

    # ── data folder ─────────────────────────────────────────────── #
    def _browse_data_dir(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Data Folder")
        if folder:
            self.data_dir_input.setText(folder)

    def _apply_data_dir(self):
        path = self.data_dir_input.text().strip()
        app_settings.set("data_dir", path)
        if path:
            self.data_dir_status.setStyleSheet(theme.label_css("success"))
            self.data_dir_status.setText(f"✓ Data folder set to: {path}")
        else:
            self.data_dir_status.setStyleSheet(theme.label_css("success"))
            self.data_dir_status.setText("✓ Reset to default local folder")

        QMessageBox.information(
            self, "Restart Required",
            "Please restart Kai for the new data folder to take effect.",
        )
        self.data_dir_changed.emit()
