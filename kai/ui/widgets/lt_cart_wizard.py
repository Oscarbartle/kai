"""Wizard step shown before the cart confirmation dialog.

Lets the user review long-term pantry items and pick which ones to buy
this trip, before the main CartConfirmDialog appears.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox, QDialog, QHBoxLayout, QLabel,
    QPushButton, QScrollArea, QVBoxLayout, QWidget,
)

from kai.ui import theme
from kai.ui.tokens import (
    SPACE_SM, SPACE_MD, SPACE_LG,
    RADIUS_MD, BORDER_W,
    FS_BODY, FS_META, FS_HEADING,
    FW_BOLD, FW_MEDIUM,
)


class LtCartWizard(QDialog):
    """Step 1 of 2 in the cart wizard: review long-term items.

    After exec(), use `.selected_items` to get the lt_items the user
    chose to include. Returns Accepted whether or not any were chosen
    (user can skip with zero selected). Returns Rejected if cancelled.
    """

    def __init__(self, lt_items: list[dict], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Cart — Step 1 of 2")
        self.setMinimumWidth(420)
        self.setMinimumHeight(320)
        self.selected_items: list[dict] = []

        t = theme.theme()
        self.setStyleSheet(f"background: {t.bg}; color: {t.text};")

        root = QVBoxLayout(self)
        root.setContentsMargins(SPACE_LG, SPACE_LG, SPACE_LG, SPACE_LG)
        root.setSpacing(SPACE_MD)

        # ── header ──────────────────────────────────────────────── #
        step_lbl = QLabel("Step 1 of 2  ·  Long-term Items")
        step_lbl.setStyleSheet(
            f"color: {t.text_faint}; font-size: {FS_META}px; font-weight: {FW_MEDIUM};"
        )
        root.addWidget(step_lbl)

        title = QLabel("Which pantry items do you need this trip?")
        title.setStyleSheet(
            f"color: {t.text}; font-size: {FS_HEADING}px; font-weight: {FW_BOLD};"
        )
        title.setWordWrap(True)
        root.addWidget(title)

        sub = QLabel(
            "These are your long-term staples. Tick anything you're running low on "
            "— they'll be added to your cart alongside the shopping list."
        )
        sub.setStyleSheet(f"color: {t.text_dim}; font-size: {FS_META}px;")
        sub.setWordWrap(True)
        root.addWidget(sub)

        # ── item list ────────────────────────────────────────────── #
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        scroll_content = QWidget()
        scroll_content.setStyleSheet("background: transparent;")
        item_layout = QVBoxLayout(scroll_content)
        item_layout.setContentsMargins(0, SPACE_SM, 0, SPACE_SM)
        item_layout.setSpacing(SPACE_SM)

        self._checkboxes: list[tuple[QCheckBox, dict]] = []

        if lt_items:
            for item in lt_items:
                name = item.get("item_name", "?")
                price = item.get("price")
                price_str = f"  ${price:.2f}" if price else ""

                row = QWidget()
                row.setObjectName("lt_wizard_row")
                row.setStyleSheet(f"""
                    QWidget#lt_wizard_row {{
                        background: {t.card};
                        border: {BORDER_W}px solid {t.border};
                        border-radius: {RADIUS_MD}px;
                    }}
                """)
                row_layout = QHBoxLayout(row)
                row_layout.setContentsMargins(SPACE_MD, SPACE_SM, SPACE_MD, SPACE_SM)
                row_layout.setSpacing(SPACE_SM)

                cb = QCheckBox()
                cb.setStyleSheet(theme.checkbox_css())
                row_layout.addWidget(cb)

                name_lbl = QLabel(name)
                name_lbl.setStyleSheet(f"color: {t.text}; font-size: {FS_BODY}px;")
                row_layout.addWidget(name_lbl, 1)

                if price_str:
                    price_lbl = QLabel(price_str)
                    price_lbl.setStyleSheet(
                        f"color: {t.text_dim}; font-size: {FS_META}px;"
                    )
                    row_layout.addWidget(price_lbl)

                item_layout.addWidget(row)
                self._checkboxes.append((cb, item))
        else:
            empty = QLabel("No long-term items for this list.")
            empty.setStyleSheet(f"color: {t.text_faint}; font-size: {FS_BODY}px;")
            item_layout.addWidget(empty)

        item_layout.addStretch()
        scroll.setWidget(scroll_content)
        root.addWidget(scroll, 1)

        # ── footer ───────────────────────────────────────────────── #
        footer = QHBoxLayout()
        footer.setSpacing(SPACE_SM)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setProperty("btn", "secondary")
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.clicked.connect(self.reject)
        footer.addWidget(cancel_btn)

        footer.addStretch()

        skip_btn = QPushButton("Skip  →")
        skip_btn.setProperty("btn", "secondary")
        skip_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        skip_btn.setToolTip("Continue without adding any long-term items")
        skip_btn.clicked.connect(self._on_skip)
        footer.addWidget(skip_btn)

        continue_btn = QPushButton("Add Selected  →")
        continue_btn.setProperty("btn", "primary")
        continue_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        continue_btn.clicked.connect(self._on_continue)
        footer.addWidget(continue_btn)

        root.addLayout(footer)

    def _on_skip(self):
        self.selected_items = []
        self.accept()

    def _on_continue(self):
        self.selected_items = [item for cb, item in self._checkboxes if cb.isChecked()]
        self.accept()
