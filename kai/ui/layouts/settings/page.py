from kai.ui import theme
from kai.core import settings as app_settings
from kai.ui.layouts.settings.theme_editor import ThemeEditorDialog
from kai.ui.tokens import SPACE_SM, SPACE_LG, SPACE_MD, RADIUS_MD

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QComboBox, QSpinBox,
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
        root.setContentsMargins(SPACE_LG, SPACE_LG, SPACE_LG, SPACE_LG)
        root.setSpacing(SPACE_MD)

        def _card():
            w = QWidget()
            w.setObjectName("settings_card")
            w.setStyleSheet(theme.inline_card_css("settings_card", radius=RADIUS_MD))
            lay = QVBoxLayout(w)
            lay.setContentsMargins(SPACE_LG, SPACE_LG, SPACE_LG, SPACE_LG)
            lay.setSpacing(SPACE_MD)
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
        window_lbl = QLabel("Flag cheapest in last … days")
        window_lbl.setProperty("role", "dim")
        gen_lay.addWidget(window_lbl)
        window_row = QHBoxLayout()
        window_row.setSpacing(SPACE_SM)
        self.history_window_spin = QSpinBox()
        self.history_window_spin.setMinimum(1)
        self.history_window_spin.setMaximum(365)
        self.history_window_spin.setValue(int(app_settings.get("price_history_window_days") or 30))
        self.history_window_spin.setFixedHeight(34)
        self.history_window_spin.setToolTip("Items at their lowest price in this window get a badge")
        self.history_window_spin.valueChanged.connect(
            lambda v: app_settings.set("price_history_window_days", v)
        )
        window_row.addWidget(self.history_window_spin)
        window_row.addStretch()
        gen_lay.addLayout(window_row)

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

        # ── Card 2: Appearance ───────────────────────────────── #
        app_card, app_lay = _card()
        app_lay.addWidget(_slbl("Appearance"))

        theme_lbl = QLabel("Active theme")
        theme_lbl.setProperty("role", "dim")
        app_lay.addWidget(theme_lbl)

        theme_row = QHBoxLayout()
        theme_row.setSpacing(SPACE_SM)
        self.theme_combo = QComboBox()
        self.theme_combo.setFixedHeight(34)
        self._refresh_theme_combo()
        self.theme_combo.currentTextChanged.connect(self._on_theme_changed)
        theme_row.addWidget(self.theme_combo, 1)

        edit_btn = QPushButton("Edit…")
        edit_btn.setProperty("btn", "secondary")
        edit_btn.setFixedHeight(34)
        edit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        edit_btn.clicked.connect(self._open_edit_theme)
        theme_row.addWidget(edit_btn)

        new_btn = QPushButton("New…")
        new_btn.setProperty("btn", "secondary")
        new_btn.setFixedHeight(34)
        new_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        new_btn.clicked.connect(self._open_new_theme)
        theme_row.addWidget(new_btn)

        app_lay.addLayout(theme_row)
        root.addWidget(app_card)

    # ── helpers ────────────────────────────────────────────────────── #
    def refresh_base_combo(self):
        self._refresh_theme_combo()

    def _refresh_theme_combo(self):
        self.theme_combo.blockSignals(True)
        self.theme_combo.clear()
        self.theme_combo.addItems([n.capitalize() for n in theme.theme_names()])
        self.theme_combo.setCurrentText(theme.theme().name.capitalize())
        self.theme_combo.blockSignals(False)

    def _on_theme_changed(self, name: str):
        theme.set_theme(name.lower())
        self.theme_changed.emit()

    def _open_edit_theme(self):
        current = theme.theme().name
        dlg = ThemeEditorDialog(self, edit_name=current if not theme.is_builtin(current) else None)
        dlg.theme_changed.connect(self._after_theme_dialog)
        dlg.exec()

    def _open_new_theme(self):
        dlg = ThemeEditorDialog(self)
        dlg.theme_changed.connect(self._after_theme_dialog)
        dlg.exec()

    def _after_theme_dialog(self):
        self._refresh_theme_combo()
        self.theme_changed.emit()

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
