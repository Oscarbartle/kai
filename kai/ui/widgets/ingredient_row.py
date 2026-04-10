from kai.ui import theme

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSpinBox, QDoubleSpinBox, QComboBox, QStackedWidget, QCheckBox,
    QSizePolicy, QCompleter,
)
from PySide6.QtGui import QCursor
from PySide6.QtCore import Qt, QStringListModel


class IngredientRow(QWidget):
    """Single row for mapping a scraped ingredient to an existing item."""

    def __init__(self, raw_text: str, existing_items: list[str],
                 best_match: str | None = None):
        super().__init__()
        self.raw_text = raw_text
        self._existing_items = list(existing_items)
        self._omitted = False

        t = theme.theme()

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 10)
        root.setSpacing(8)

        # ── top row: raw text + omit button ──────────────────── #
        top = QHBoxLayout()
        top.setSpacing(8)
        top.setContentsMargins(0, 0, 0, 0)

        self._raw_label = QLabel(raw_text)
        self._raw_label.setWordWrap(True)
        self._raw_label.setStyleSheet(f"color: {t.text}; font-size: 12px; font-weight: 600;")
        top.addWidget(self._raw_label, 1)

        self._omit_btn = QPushButton("Omit")
        self._omit_btn.setFixedHeight(26)
        self._omit_btn.setFixedWidth(56)
        self._omit_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._omit_btn.setCheckable(True)
        self._omit_btn.setToolTip("Exclude this ingredient from the recipe")
        self._omit_btn.toggled.connect(self._on_omit_toggled)
        top.addWidget(self._omit_btn)

        root.addLayout(top)

        # ── bottom row: item search + amount + unit + nominal ── #
        self._controls = QWidget()
        controls_layout = QHBoxLayout(self._controls)
        controls_layout.setContentsMargins(0, 0, 0, 0)
        controls_layout.setSpacing(8)

        # searchable item combo
        self.item_combo = QComboBox()
        self.item_combo.setEditable(True)
        self.item_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.item_combo.lineEdit().setPlaceholderText("Search items…")
        self.item_combo.addItem("— None —")
        for name in sorted(existing_items):
            self.item_combo.addItem(name)

        completer = QCompleter(sorted(existing_items), self)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self.item_combo.setCompleter(completer)
        self._completer = completer

        if best_match:
            idx = self.item_combo.findText(best_match)
            if idx >= 0:
                self.item_combo.setCurrentIndex(idx)
        self.item_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.item_combo.setFixedHeight(30)
        controls_layout.addWidget(self.item_combo, 3)

        # amount spinbox (int / float stacked)
        self.amount_spin = QSpinBox()
        self.amount_spin.setMinimum(1)
        self.amount_spin.setMaximum(99999)
        self.amount_spin.setValue(1)
        self.amount_spin.setFixedHeight(30)
        self.amount_spin.setFixedWidth(64)

        self.amount_spin_float = QDoubleSpinBox()
        self.amount_spin_float.setMinimum(0.1)
        self.amount_spin_float.setMaximum(9999)
        self.amount_spin_float.setValue(1.0)
        self.amount_spin_float.setDecimals(1)
        self.amount_spin_float.setSingleStep(0.1)
        self.amount_spin_float.setFixedHeight(30)
        self.amount_spin_float.setFixedWidth(64)

        self.amount_stack = QStackedWidget()
        self.amount_stack.addWidget(self.amount_spin)
        self.amount_stack.addWidget(self.amount_spin_float)
        self.amount_stack.setCurrentIndex(0)
        self.amount_stack.setFixedWidth(64)
        controls_layout.addWidget(self.amount_stack)

        self.unit_combo = QComboBox()
        self.unit_combo.addItems(["g", "kg", "mL", "L", "ea"])
        self.unit_combo.setCurrentText("ea")
        self.unit_combo.setFixedHeight(30)
        self.unit_combo.setFixedWidth(62)
        self.unit_combo.currentTextChanged.connect(self._on_unit_changed)
        controls_layout.addWidget(self.unit_combo)

        # nominal checkbox
        self.nominal_cb = QCheckBox("Nominal")
        self.nominal_cb.setToolTip(
            "Use when an exact amount doesn't matter (e.g. olive oil, salt).\n"
            "Counted as 1 unit on shopping lists and excluded from cost totals."
        )
        self.nominal_cb.setFixedHeight(30)
        self.nominal_cb.setStyleSheet(theme.checkbox_css())
        self.nominal_cb.toggled.connect(self._on_nominal_toggled)
        controls_layout.addWidget(self.nominal_cb)

        # new item button
        self.add_item_btn = QPushButton("+ New")
        self.add_item_btn.setFixedHeight(30)
        self.add_item_btn.setFixedWidth(58)
        self.add_item_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        controls_layout.addWidget(self.add_item_btn)

        root.addWidget(self._controls)

        self._apply_style()

    # ── style ─────────────────────────────────────────────────── #

    def _apply_style(self):
        t = theme.theme()
        if self._omitted:
            self.setStyleSheet(f"""
                QWidget {{
                    background: transparent;
                    border: 1px solid {t.border};
                    border-radius: 8px;
                    opacity: 0.5;
                }}
            """)
            self._omit_btn.setStyleSheet(f"""
                QPushButton {{
                    background: {t.danger};
                    color: white;
                    border: none;
                    border-radius: 5px;
                    font-size: 11px;
                    font-weight: bold;
                }}
            """)
            self._raw_label.setStyleSheet(
                f"color: {t.text_faint}; font-size: 12px; font-weight: 600;"
                "text-decoration: line-through;"
            )
        else:
            self.setStyleSheet(f"""
                QWidget {{
                    background: {t.card};
                    border: 1px solid {t.border};
                    border-radius: 8px;
                }}
            """)
            self._omit_btn.setStyleSheet(f"""
                QPushButton {{
                    background: {t.surface};
                    color: {t.text_dim};
                    border: 1px solid {t.border};
                    border-radius: 5px;
                    font-size: 11px;
                    font-weight: 600;
                }}
                QPushButton:hover {{
                    background: {t.danger};
                    color: white;
                    border-color: {t.danger};
                }}
            """)
            self._raw_label.setStyleSheet(
                f"color: {t.text}; font-size: 12px; font-weight: 600;"
            )

    def _on_omit_toggled(self, checked):
        self._omitted = checked
        self._omit_btn.setText("Omitted" if checked else "Omit")
        self._controls.setEnabled(not checked)
        self._apply_style()

    def _on_unit_changed(self, unit):
        if unit in ("kg", "L"):
            self.amount_spin_float.setValue(float(self.amount_spin.value()))
            self.amount_stack.setCurrentIndex(1)
        else:
            self.amount_spin.setValue(max(1, int(self.amount_spin_float.value())))
            self.amount_stack.setCurrentIndex(0)

    def _on_nominal_toggled(self, checked):
        self.amount_stack.setEnabled(not checked)
        self.unit_combo.setEnabled(not checked)

    # ── public API ────────────────────────────────────────────── #

    def refresh_items(self, existing_items: list[str], auto_select: str | None = None):
        """Refresh the item combo + completer after a new item was added."""
        current = self.item_combo.currentText()
        self.item_combo.clear()
        self.item_combo.addItem("— None —")
        for name in sorted(existing_items):
            self.item_combo.addItem(name)

        self._completer.setModel(QStringListModel(sorted(existing_items), self._completer))
        self._existing_items = list(existing_items)

        if auto_select:
            idx = self.item_combo.findText(auto_select)
            if idx >= 0:
                self.item_combo.setCurrentIndex(idx)
        elif current not in ("— None —", ""):
            idx = self.item_combo.findText(current)
            if idx >= 0:
                self.item_combo.setCurrentIndex(idx)

    def is_omitted(self) -> bool:
        return self._omitted

    def get_data(self) -> dict | None:
        if self._omitted:
            return None
        item_name = self.item_combo.currentText().strip()
        if not item_name or item_name == "— None —":
            return None
        nominal = self.nominal_cb.isChecked()
        unit = self.unit_combo.currentText()
        if nominal:
            return {"item_name": item_name, "amount": 1, "unit": "ea", "nominal": True}
        if unit in ("kg", "L"):
            amount = self.amount_spin_float.value()
        else:
            amount = self.amount_spin.value()
        return {"item_name": item_name, "amount": amount, "unit": unit, "nominal": False}
