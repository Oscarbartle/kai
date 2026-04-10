from kai.ui import theme
from kai.ui.theme import Palette

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QScrollArea, QColorDialog, QGridLayout, QComboBox, QFrame,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor


_GROUPS = [
    ("Surfaces", [
        ("bg", "Background"),
        ("surface", "Surface"),
        ("card", "Card"),
        ("border", "Border"),
    ]),
    ("Text", [
        ("text", "Primary"),
        ("text_dim", "Dimmed"),
        ("text_faint", "Faint"),
    ]),
    ("Accents", [
        ("accent", "Accent"),
        ("accent_fg", "Accent text"),
        ("success", "Success"),
        ("warning", "Warning"),
        ("danger", "Danger"),
    ]),
    ("Buttons", [
        ("btn_bg", "Background"),
        ("btn_fg", "Text"),
        ("btn_hover", "Hover"),
        ("btn_pressed", "Pressed"),
    ]),
    ("List Highlight", [
        ("list_hl", "Selection"),
        ("list_hl_fg", "Selection text"),
    ]),
]


class ColorSwatch(QPushButton):
    """A small color button that opens QColorDialog on click."""

    color_changed = Signal(str)

    def __init__(self, hex_color: str, parent=None):
        super().__init__(parent)
        self._color = hex_color
        self.setFixedSize(36, 36)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._apply()
        self.clicked.connect(self._pick)

    def _apply(self):
        self.setStyleSheet(
            f"background-color: {self._color}; border: 2px solid #555; border-radius: 6px;"
        )
        self.setToolTip(self._color)

    def _pick(self):
        c = QColorDialog.getColor(QColor(self._color), self, "Pick colour")
        if c.isValid():
            self._color = c.name()
            self._apply()
            self.color_changed.emit(self._color)

    def color(self) -> str:
        return self._color

    def set_color(self, hex_color: str):
        self._color = hex_color
        self._apply()


class ThemeEditor(QWidget):
    theme_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._swatches: dict[str, ColorSwatch] = {}
        self._build()

    def _build(self):
        t = theme.theme()
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        def _slbl(text):
            lbl = QLabel(text)
            lbl.setStyleSheet(theme.section_label_css())
            return lbl

        def _divider():
            line = QFrame()
            line.setFrameShape(QFrame.Shape.HLine)
            line.setStyleSheet(theme.divider_line_css())
            return line

        root.addWidget(_slbl("Theme Editor"))

        base_lbl = QLabel("Start from")
        base_lbl.setProperty("role", "dim")
        root.addWidget(base_lbl)
        self.base_combo = QComboBox()
        self.base_combo.addItems([n.capitalize() for n in theme.theme_names()])
        self.base_combo.setCurrentText(theme.theme().name.capitalize())
        self.base_combo.setFixedHeight(34)
        self.base_combo.currentTextChanged.connect(self._load_base)
        root.addWidget(self.base_combo)

        name_lbl = QLabel("Theme name")
        name_lbl.setProperty("role", "dim")
        root.addWidget(name_lbl)
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("my-theme")
        self.name_input.setFixedHeight(34)
        root.addWidget(self.name_input)

        root.addWidget(_divider())

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; } QWidget { background: transparent; }")
        inner = QWidget()
        grid = QGridLayout(inner)
        grid.setContentsMargins(0, 4, 0, 4)
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(10)

        row = 0
        for group_name, tokens in _GROUPS:
            group_lbl = QLabel(group_name)
            group_lbl.setStyleSheet(
                f"color: {t.accent}; font-size: 10px; font-weight: 700; "
                "letter-spacing: 0.8px; text-transform: uppercase; padding-top: 6px;"
            )
            grid.addWidget(group_lbl, row, 0, 1, 3)
            row += 1

            for attr, display in tokens:
                lbl = QLabel(display)
                lbl.setProperty("role", "body")
                swatch = ColorSwatch(getattr(t, attr))
                hex_lbl = QLabel(getattr(t, attr))
                hex_lbl.setProperty("role", "dim")
                hex_lbl.setFixedWidth(80)
                swatch.color_changed.connect(lambda c, h=hex_lbl: h.setText(c))
                self._swatches[attr] = swatch

                grid.addWidget(lbl, row, 0)
                grid.addWidget(swatch, row, 1)
                grid.addWidget(hex_lbl, row, 2)
                row += 1

        grid.setRowStretch(row, 1)
        scroll.setWidget(inner)
        root.addWidget(scroll, 1)

        root.addWidget(_divider())

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        self.status_label = QLabel("")
        self.status_label.setProperty("role", "dim")
        self.delete_btn = QPushButton("Delete")
        self.delete_btn.setProperty("btn", "secondary")
        self.delete_btn.setFixedHeight(36)
        self.delete_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.delete_btn.clicked.connect(self._delete_theme)
        save_btn = QPushButton("Save && Apply")
        save_btn.setProperty("btn", "primary")
        save_btn.setFixedHeight(36)
        save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        save_btn.clicked.connect(self._save_theme)
        btn_row.addWidget(self.status_label, 1)
        btn_row.addWidget(self.delete_btn)
        btn_row.addWidget(save_btn)
        root.addLayout(btn_row)

    def _load_base(self, name: str):
        p = theme.PALETTES.get(name.lower())
        if not p:
            return
        for attr, swatch in self._swatches.items():
            swatch.set_color(getattr(p, attr))
            swatch.color_changed.emit(getattr(p, attr))

    def _save_theme(self):
        name = self.name_input.text().strip().lower().replace(" ", "-")
        if not name:
            self.status_label.setStyleSheet(theme.label_css("danger"))
            self.status_label.setText("Enter a theme name")
            return
        if theme.is_builtin(name):
            self.status_label.setStyleSheet(theme.label_css("danger"))
            self.status_label.setText("Can't overwrite built-in themes")
            return

        palette = Palette(
            name=name,
            **{attr: sw.color() for attr, sw in self._swatches.items()},
        )
        theme.save_custom_palette(palette)
        theme.set_theme(name)
        self.status_label.setStyleSheet(theme.label_css("success"))
        self.status_label.setText(f"Saved '{name}'")
        self.theme_changed.emit()

    def _delete_theme(self):
        name = self.name_input.text().strip().lower().replace(" ", "-")
        if not name or theme.is_builtin(name) or name not in theme.PALETTES:
            self.status_label.setStyleSheet(theme.label_css("danger"))
            self.status_label.setText("Select a custom theme to delete")
            return
        theme.delete_custom_palette(name)
        theme.set_theme("graphite")
        self.status_label.setStyleSheet(theme.label_css("success"))
        self.status_label.setText(f"Deleted '{name}'")
        self.theme_changed.emit()

    def refresh_base_combo(self):
        self.base_combo.blockSignals(True)
        self.base_combo.clear()
        self.base_combo.addItems([n.capitalize() for n in theme.theme_names()])
        self.base_combo.setCurrentText(theme.theme().name.capitalize())
        self.base_combo.blockSignals(False)
