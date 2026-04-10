"""Confirmation and progress dialogs for Woolworths cart automation."""
from __future__ import annotations

import webbrowser

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QProgressBar,
    QPushButton, QScrollArea, QVBoxLayout, QWidget,
)

from kai.ui import theme


class CartConfirmDialog(QDialog):
    """Shows the list of items that will be added to the Woolworths cart.

    After exec(), use `.accepted_items` to get the items the user approved.
    """

    def __init__(self, items: list[dict], parent=None):
        """items: list of {name, stock_code, qty, units_needed, price}"""
        super().__init__(parent)
        self.setWindowTitle("Add to Woolworths Cart")
        self.setMinimumWidth(460)
        self.setMinimumHeight(300)
        self.accepted_items: list[dict] = [i for i in items if i.get("stock_code")]

        t = theme.theme()
        self.setStyleSheet(f"QDialog {{ background: {t.bg}; color: {t.text}; }}")

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(14)

        # header
        has = len(self.accepted_items)
        skipped = len(items) - has
        header_lbl = QLabel(f"<b>Add {has} item{'s' if has != 1 else ''} to your Woolworths cart?</b>")
        header_lbl.setStyleSheet(f"color: {t.text}; font-size: 14px;")
        root.addWidget(header_lbl)

        if skipped:
            skip_lbl = QLabel(f"{skipped} item{'s' if skipped != 1 else ''} skipped — no stock code linked.")
            skip_lbl.setStyleSheet(f"color: {t.text_faint}; font-size: 11px;")
            root.addWidget(skip_lbl)

        # scrollable item list
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(theme.scrollbar_css())

        list_widget = QWidget()
        list_widget.setObjectName("confirm_list")
        list_widget.setStyleSheet(theme.card_css("confirm_list"))
        list_lay = QVBoxLayout(list_widget)
        list_lay.setContentsMargins(12, 12, 12, 12)
        list_lay.setSpacing(6)

        for item in items:
            row = QHBoxLayout()
            row.setSpacing(8)

            has_code = bool(item.get("stock_code"))
            color = t.text if has_code else t.text_faint

            name_lbl = QLabel(item["name"])
            name_lbl.setStyleSheet(f"color: {color}; font-size: 12px;")
            row.addWidget(name_lbl, 1)

            qty_lbl = QLabel(f"× {item.get('units_needed', item.get('qty', 1))} pkg")
            qty_lbl.setStyleSheet(f"color: {t.text_dim if has_code else t.text_faint}; font-size: 11px;")
            row.addWidget(qty_lbl)

            if item.get("price") is not None and has_code:
                price_lbl = QLabel(f"${item['price']:.2f}")
                price_lbl.setStyleSheet(f"color: {t.accent}; font-size: 12px; font-weight: bold;")
                row.addWidget(price_lbl)
            elif not has_code:
                no_code_lbl = QLabel("no stock code")
                no_code_lbl.setStyleSheet(f"color: {t.text_faint}; font-size: 10px; font-style: italic;")
                row.addWidget(no_code_lbl)

            list_lay.addLayout(row)

        list_lay.addStretch()
        scroll.setWidget(list_widget)
        root.addWidget(scroll, 1)

        # total
        total = sum(i["price"] for i in self.accepted_items if i.get("price") is not None)
        if total:
            total_lbl = QLabel(f"<b>Estimated total: ${total:.2f}</b>")
            total_lbl.setStyleSheet(f"color: {t.text}; font-size: 13px;")
            total_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
            root.addWidget(total_lbl)

        # buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFixedHeight(36)
        cancel_btn.setStyleSheet(theme.button_css(primary=False))
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.clicked.connect(self.reject)

        add_btn = QPushButton(f"Add {has} Item{'s' if has != 1 else ''} to Cart")
        add_btn.setFixedHeight(36)
        add_btn.setStyleSheet(theme.button_css(primary=True))
        add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_btn.setEnabled(has > 0)
        add_btn.clicked.connect(self.accept)

        btn_row.addWidget(cancel_btn)
        btn_row.addStretch()
        btn_row.addWidget(add_btn)
        root.addLayout(btn_row)


class CartProgressDialog(QDialog):
    """Live progress dialog shown while items are being added to the Woolworths cart."""

    def __init__(self, total: int, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Adding to Woolworths Cart…")
        self.setMinimumWidth(440)
        self.setMinimumHeight(300)
        self.setWindowFlag(Qt.WindowType.WindowCloseButtonHint, False)
        self._total = total
        self._done = 0

        t = theme.theme()
        self.setStyleSheet(f"QDialog {{ background: {t.bg}; color: {t.text}; }}")

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(14)

        self._header = QLabel(f"Adding items to your Woolworths cart…")
        self._header.setStyleSheet(f"color: {t.text}; font-size: 13px; font-weight: bold;")
        root.addWidget(self._header)

        self._progress = QProgressBar()
        self._progress.setMaximum(total)
        self._progress.setValue(0)
        self._progress.setFixedHeight(10)
        self._progress.setTextVisible(False)
        self._progress.setStyleSheet(f"""
            QProgressBar {{
                background: {t.border};
                border-radius: 5px;
                border: none;
            }}
            QProgressBar::chunk {{
                background: {t.accent};
                border-radius: 5px;
            }}
        """)
        root.addWidget(self._progress)

        # scrollable log
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(theme.scrollbar_css())

        self._log_widget = QWidget()
        self._log_widget.setObjectName("cart_log")
        self._log_widget.setStyleSheet(theme.card_css("cart_log"))
        self._log_lay = QVBoxLayout(self._log_widget)
        self._log_lay.setContentsMargins(12, 10, 12, 10)
        self._log_lay.setSpacing(4)
        self._log_lay.addStretch()

        scroll.setWidget(self._log_widget)
        root.addWidget(scroll, 1)

        self._summary_lbl = QLabel("")
        self._summary_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
        self._summary_lbl.hide()
        root.addWidget(self._summary_lbl)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        self._close_btn = QPushButton("Close")
        self._close_btn.setFixedHeight(36)
        self._close_btn.setStyleSheet(theme.button_css(primary=False))
        self._close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._close_btn.setEnabled(False)
        self._close_btn.clicked.connect(self.accept)

        self._cart_btn = QPushButton("Open Cart")
        self._cart_btn.setFixedHeight(36)
        self._cart_btn.setStyleSheet(theme.button_css(primary=True))
        self._cart_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._cart_btn.hide()
        self._cart_btn.clicked.connect(self._open_cart)

        btn_row.addWidget(self._close_btn)
        btn_row.addStretch()
        btn_row.addWidget(self._cart_btn)
        root.addLayout(btn_row)

    def mark_item(self, name: str, success: bool):
        """Called from the worker thread via a queued signal."""
        t = theme.theme()
        self._done += 1
        self._progress.setValue(self._done)

        icon = "✓" if success else "✗"
        color = t.success if success else t.danger
        row = QLabel(f"<span style='color:{color}; font-weight:bold;'>{icon}</span>  {name}")
        row.setStyleSheet(f"color: {t.text}; font-size: 12px;")
        # insert before the stretch
        self._log_lay.insertWidget(self._log_lay.count() - 1, row)

    def on_finished(self, ok: int, fail: int):
        """Called when all add-to-cart calls have completed."""
        t = theme.theme()
        total = ok + fail

        if fail == 0:
            self._header.setText(f"Done! {ok} item{'s' if ok != 1 else ''} added to your cart.")
            color = t.success
        else:
            self._header.setText(f"{ok}/{total} items added — {fail} failed.")
            color = t.danger if ok == 0 else t.warning

        summary_html = (
            f"<span style='color:{color}; font-size:12px;'>"
            f"{ok} added, {fail} failed</span>"
        )
        self._summary_lbl.setText(summary_html)
        self._summary_lbl.show()

        self._close_btn.setEnabled(True)
        self._cart_btn.show()

    def _open_cart(self):
        QDesktopServices.openUrl(QUrl("https://www.woolworths.co.nz/reviewtrolley"))
