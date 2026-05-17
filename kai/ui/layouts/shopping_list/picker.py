from kai.objects.recipe import Recipe
from kai.objects.item import Item
from kai.objects.shopping_list import ShoppingList
from kai.core.backend import get_recipe, get_item, get_shopping_list
from kai.ui import theme
from kai.ui.layouts.shopping_list.cards import RecipePickerCard, SavedListCard
from kai.ui.tokens import SPACE_SM, SPACE_MD, RADIUS_SM, H_ROW, FS_BODY, FS_META

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QStackedWidget,
    QLabel,
    QPushButton,
    QButtonGroup,
    QLineEdit,
    QScrollArea,
    QSizePolicy,
    QSpinBox, QDoubleSpinBox,
)
from PySide6.QtGui import QCursor, QIcon
from PySide6.QtCore import Qt, QSize

from pathlib import Path

_ICONS = Path(__file__).resolve().parent.parent.parent.parent / "icons"


class ShoppingListPickerMixin:
    # ── left panel: recipe / item / saved-list tabs ── #

    def _make_tab_btn(self, icon_file: str, tooltip: str) -> QPushButton:
        from kai.ui.widgets.nav_button import _colorize_svg
        t = theme.theme()
        btn = QPushButton()
        btn.setCheckable(True)
        btn.setFixedSize(80, 32)
        btn.setToolTip(tooltip)
        btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._tab_icons[icon_file] = (btn, icon_file, tooltip)
        icon = _colorize_svg(str(_ICONS / icon_file), t.text_dim, size=18)
        if icon:
            btn.setIcon(icon)
            btn.setIconSize(QSize(18, 18))
        self._apply_tab_btn_style(btn, False)
        return btn

    def _apply_tab_btn_style(self, btn: QPushButton, checked: bool):
        t = theme.theme()
        color = t.card if checked else t.bg
        border_bottom = f"border-bottom: 2px solid {t.accent};" if checked else "border-bottom: 2px solid transparent;"
        btn.setStyleSheet(f"""
            QPushButton {{
                background: {color};
                border: {1}px solid {t.border};
                border-bottom: none;
                border-top-left-radius: {SPACE_SM}px;
                border-top-right-radius: {SPACE_SM}px;
                padding: 0px;
            }}
        """)

    def _switch_tab(self, index: int):
        from kai.ui.widgets.nav_button import _colorize_svg
        self.left_stack.setCurrentIndex(index)
        for i, btn in enumerate(self._tab_btns):
            checked = i == index
            t = theme.theme()
            color = t.card if checked else t.bg
            btn.setChecked(checked)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: {color};
                    border: 1px solid {t.border};
                    border-bottom: {'none' if checked else f'1px solid {t.border}'};
                    border-top-left-radius: {SPACE_SM}px;
                    border-top-right-radius: {SPACE_SM}px;
                    padding: 0px;
                }}
            """)
            # update icon colour: accent when active, dim otherwise
            icon_file = list(self._tab_icons.keys())[i]
            icon = _colorize_svg(str(_ICONS / icon_file), t.accent if checked else t.text_dim, size=18)
            btn.setIcon(icon)
        if index == 1:
            self._refresh_item_rows()
        elif index == 2:
            self._refresh_saved_list()

    def _build_left_panel(self):
        self.left_panel = QWidget()
        self.left_panel.setObjectName("page_panel")
        self.left_panel.setMinimumWidth(200)
        left_layout = QVBoxLayout(self.left_panel)
        left_layout.setContentsMargins(SPACE_MD, SPACE_MD, SPACE_MD, SPACE_MD)
        left_layout.setSpacing(0)

        # custom tab bar
        self._tab_icons = {}
        tab_bar = QHBoxLayout()
        tab_bar.setContentsMargins(0, 0, 0, 0)
        tab_bar.setSpacing(2)
        self._tab_btns = [
            self._make_tab_btn("recipes.svg", "Recipes"),
            self._make_tab_btn("items.svg", "Items"),
            self._make_tab_btn("star.svg", "Saved lists"),
        ]
        for i, btn in enumerate(self._tab_btns):
            tab_bar.addWidget(btn)
            btn.clicked.connect(lambda _, idx=i: self._switch_tab(idx))
        tab_bar.addStretch()
        left_layout.addLayout(tab_bar)

        # stacked content (replaces QTabWidget pane)
        self.left_stack = QStackedWidget()
        t = theme.theme()
        self.left_stack.setStyleSheet(f"""
            QStackedWidget {{
                background: {t.bg};
                border: 1px solid {t.border};
                border-radius: {RADIUS_SM}px;
                border-top-left-radius: 0px;
            }}
        """)
        left_layout.addWidget(self.left_stack, 1)

        # alias so existing code using left_tabs still works
        self.left_tabs = type('_FakeTabs', (), {
            'setCurrentIndex': lambda s, i: self._switch_tab(i),
            'currentIndex':    lambda s: self.left_stack.currentIndex(),
        })()

        # ── tab 0: Recipes ────────────────────────────────────── #
        self.picker_page = QWidget()
        picker_layout = QVBoxLayout(self.picker_page)
        picker_layout.setContentsMargins(SPACE_SM, SPACE_SM, SPACE_SM, 0)
        picker_layout.setSpacing(SPACE_SM)

        self.recipe_search = QLineEdit()
        self.recipe_search.setPlaceholderText("Search recipes…")
        self.recipe_search.setClearButtonEnabled(True)
        picker_layout.addWidget(self.recipe_search)

        self.tag_scroll = QScrollArea()
        self.tag_scroll.setWidgetResizable(True)
        self.tag_scroll.setFixedHeight(34)
        self.tag_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.tag_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.tag_scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        self.tag_bar_widget = QWidget()
        self.tag_bar_widget.setStyleSheet("background: transparent;")
        self.tag_bar_layout = QHBoxLayout(self.tag_bar_widget)
        self.tag_bar_layout.setContentsMargins(0, 0, 0, 0)
        self.tag_bar_layout.setSpacing(4)
        self.tag_bar_layout.addStretch()
        self.tag_scroll.setWidget(self.tag_bar_widget)
        picker_layout.addWidget(self.tag_scroll)

        self._active_tag = None
        self._recipe_cards = []

        self.recipe_scroll = QScrollArea()
        self.recipe_scroll.setWidgetResizable(True)
        self.recipe_scroll_widget = QWidget()
        self.recipe_scroll_widget.setStyleSheet("background: transparent;")
        self.recipe_scroll_layout = QVBoxLayout(self.recipe_scroll_widget)
        self.recipe_scroll_layout.setContentsMargins(2, 2, 2, 2)
        self.recipe_scroll_layout.setSpacing(6)
        self.recipe_scroll.setWidget(self.recipe_scroll_widget)
        picker_layout.addWidget(self.recipe_scroll, 1)

        self.left_stack.addWidget(self.picker_page)

        # ── tab 1: Items ──────────────────────────────────────── #
        self.item_picker_page = QWidget()
        item_picker_layout = QVBoxLayout(self.item_picker_page)
        item_picker_layout.setContentsMargins(SPACE_SM, SPACE_SM, SPACE_SM, 0)
        item_picker_layout.setSpacing(SPACE_SM)

        self.item_search = QLineEdit()
        self.item_search.setPlaceholderText("Search items…")
        self.item_search.setClearButtonEnabled(True)
        item_picker_layout.addWidget(self.item_search)

        self.item_tag_scroll = QScrollArea()
        self.item_tag_scroll.setWidgetResizable(True)
        self.item_tag_scroll.setFixedHeight(34)
        self.item_tag_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.item_tag_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.item_tag_scroll.setStyleSheet(
            "QScrollArea { border: none; background: transparent; }"
        )
        self.item_tag_bar_widget = QWidget()
        self.item_tag_bar_widget.setStyleSheet("background: transparent;")
        self.item_tag_bar_layout = QHBoxLayout(self.item_tag_bar_widget)
        self.item_tag_bar_layout.setContentsMargins(0, 0, 0, 0)
        self.item_tag_bar_layout.setSpacing(4)
        self.item_tag_bar_layout.addStretch()
        self.item_tag_scroll.setWidget(self.item_tag_bar_widget)
        item_picker_layout.addWidget(self.item_tag_scroll)

        self._active_item_tag = None

        self.item_scroll = QScrollArea()
        self.item_scroll.setWidgetResizable(True)
        self.item_scroll_widget = QWidget()
        self.item_scroll_widget.setStyleSheet("background: transparent;")
        self.item_scroll_layout = QVBoxLayout(self.item_scroll_widget)
        self.item_scroll_layout.setContentsMargins(2, 2, 2, 2)
        self.item_scroll_layout.setSpacing(4)
        self.item_scroll.setWidget(self.item_scroll_widget)
        item_picker_layout.addWidget(self.item_scroll, 1)

        self._item_rows = []
        self.left_stack.addWidget(self.item_picker_page)

        # ── tab 2: Saved Lists ────────────────────────────────── #
        self.saved_page = QWidget()
        saved_layout = QVBoxLayout(self.saved_page)
        saved_layout.setContentsMargins(SPACE_SM, SPACE_SM, SPACE_SM, 0)
        saved_layout.setSpacing(SPACE_SM)

        self.saved_scroll = QScrollArea()
        self.saved_scroll.setWidgetResizable(True)
        self.saved_scroll_widget = QWidget()
        self.saved_scroll_widget.setStyleSheet("background: transparent;")
        self.saved_scroll_layout = QVBoxLayout(self.saved_scroll_widget)
        self.saved_scroll_layout.setContentsMargins(2, 2, 2, 2)
        self.saved_scroll_layout.setSpacing(6)
        self.saved_scroll.setWidget(self.saved_scroll_widget)
        saved_layout.addWidget(self.saved_scroll, 1)

        self.left_stack.addWidget(self.saved_page)

        self.h_splitter.insertWidget(0, self.left_panel)
        self.h_splitter.setStretchFactor(0, 1)

        self._switch_tab(0)
        self._refresh_recipe_cards()

    # ── recipe picker ──────────────────────────────────────────── #

    def _refresh_recipe_cards(self):
        while self.recipe_scroll_layout.count():
            child = self.recipe_scroll_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        self._recipe_cards = []
        recipes = get_recipe().get_recipes()
        recipes.sort(key=lambda x: x[0])

        if not recipes:
            empty = QLabel("No recipes yet — create some first!")
            empty.setProperty("role", "faint")
            self.recipe_scroll_layout.addWidget(empty)
        else:
            for name, _ in recipes:
                card = RecipePickerCard(name, self._add_recipe_to_cart)
                self._recipe_cards.append(card)
                self.recipe_scroll_layout.addWidget(card)

        self.recipe_scroll_layout.addStretch()
        self._refresh_tag_bar()
        self._active_tag = None
        self.recipe_search.clear()

    def _refresh_tag_bar(self):
        while self.tag_bar_layout.count():
            child = self.tag_bar_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        t = theme.theme()
        tags = sorted(get_recipe().get_recipe_tags())

        if not tags:
            self.tag_scroll.setVisible(False)
            return

        self.tag_scroll.setVisible(True)

        def chip_css() -> str:
            return f"""
                QPushButton {{
                    background-color: {t.surface};
                    color: {t.text_dim};
                    border: 1px solid {t.border};
                    border-radius: 13px;
                    padding: 0 {SPACE_MD}px;
                    font-size: {FS_META}px;
                    font-weight: 600;
                }}
                QPushButton:hover {{
                    background-color: {t.border};
                    color: {t.text};
                }}
                QPushButton:checked {{
                    background-color: {t.accent};
                    color: {t.accent_fg};
                    border-color: {t.accent};
                }}
            """

        fav_btn = QPushButton("★ Favourites")
        fav_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        fav_btn.setCheckable(True)
        fav_btn.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        fav_btn.setFixedHeight(26)
        fav_btn.setStyleSheet(chip_css())
        fav_btn.clicked.connect(lambda checked: self._on_tag_clicked("★ Favourites", checked))
        self.tag_bar_layout.addWidget(fav_btn)

        for tag in tags:
            btn = QPushButton(tag)
            btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            btn.setCheckable(True)
            btn.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
            btn.setFixedHeight(26)
            btn.setStyleSheet(chip_css())
            btn.clicked.connect(lambda checked, tg=tag: self._on_tag_clicked(tg, checked))
            self.tag_bar_layout.addWidget(btn)

        self.tag_bar_layout.addStretch()

    def _on_tag_clicked(self, tag, checked):
        self._active_tag = tag if checked else None

        for i in range(self.tag_bar_layout.count()):
            w = self.tag_bar_layout.itemAt(i).widget()
            if w and isinstance(w, QPushButton) and w.text() != tag:
                w.setChecked(False)

        self._filter_recipe_cards()

    def _filter_recipe_cards(self, _text=None):
        search = self.recipe_search.text().lower().strip()
        for card in self._recipe_cards:
            name_match = not search or search in card._name.lower()
            if self._active_tag == "★ Favourites":
                doc = get_recipe().get_recipe_details(card._name)
                tag_match = doc.get("is_favourite", False) if doc else False
            else:
                tag_match = not self._active_tag or self._active_tag in card.tags
            card.setVisible(name_match and tag_match)

    # ── item picker ────────────────────────────────────────────── #

    def _show_item_picker(self):
        self.left_tabs.setCurrentIndex(1)

    def _refresh_item_rows(self):
        while self.item_scroll_layout.count():
            child = self.item_scroll_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        self._item_rows = []
        t = theme.theme()
        item_obj = get_item()
        names = sorted(item_obj.get_item_names())

        for name in names:
            row = QWidget()
            row.setObjectName("item_pick_row")
            row.setFixedHeight(H_ROW)
            row.setStyleSheet(theme.inline_card_css("item_pick_row", radius=RADIUS_SM))
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(SPACE_MD, 0, SPACE_SM, 0)
            row_layout.setSpacing(SPACE_SM)

            label = QLabel(name)
            label.setStyleSheet(f"color: {t.text}; font-size: {FS_BODY}px;")
            row_layout.addWidget(label, 1)

            details = item_obj.get_item_details(name)
            sold_by_weight = (details or {}).get("sold_by_weight", False)
            default_weight = (details or {}).get("default_weight_kg") or 0.5

            if sold_by_weight:
                spin = QDoubleSpinBox()
                spin.setRange(0.1, 50.0)
                spin.setSingleStep(0.1)
                spin.setDecimals(2)
                spin.setValue(float(default_weight))
                spin.setSuffix(" kg")
                spin.setFixedWidth(80)
                spin.setFixedHeight(28)
                row_layout.addWidget(spin)
                add_btn = QPushButton("+")
                add_btn.setFixedSize(28, 28)
                add_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
                add_btn.setStyleSheet(theme.mini_primary_btn_css(radius=14))
                add_btn.clicked.connect(
                    lambda checked, n=name, s=spin: self._add_extra_item(n, weight_kg=s.value())
                )
            else:
                spin = QSpinBox()
                spin.setMinimum(1)
                spin.setMaximum(99)
                spin.setValue(1)
                spin.setFixedWidth(50)
                spin.setFixedHeight(28)
                row_layout.addWidget(spin)
                add_btn = QPushButton("+")
                add_btn.setFixedSize(28, 28)
                add_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
                add_btn.setStyleSheet(theme.mini_primary_btn_css(radius=14))
                add_btn.clicked.connect(
                    lambda checked, n=name, s=spin: self._add_extra_item(n, units=s.value())
                )
            row_layout.addWidget(add_btn)

            row._item_name = name
            row._item_tags = (details or {}).get("tags", [])
            self._item_rows.append(row)
            self.item_scroll_layout.addWidget(row)

        self.item_scroll_layout.addStretch()
        self._refresh_item_tag_bar()

    def _filter_item_rows(self, _text=None):
        search = self.item_search.text().lower().strip()
        for row in self._item_rows:
            name_match = not search or search in row._item_name.lower()
            tag_match = not self._active_item_tag or self._active_item_tag in row._item_tags
            row.setVisible(name_match and tag_match)

    def _refresh_item_tag_bar(self):
        while self.item_tag_bar_layout.count():
            child = self.item_tag_bar_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        t = theme.theme()
        tags = sorted(get_item().get_item_tags())

        if not tags:
            self.item_tag_scroll.setVisible(False)
            return

        self.item_tag_scroll.setVisible(True)
        for tag in tags:
            btn = QPushButton(tag)
            btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            btn.setCheckable(True)
            btn.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
            btn.setFixedHeight(26)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {t.surface};
                    color: {t.text_dim};
                    border: 1px solid {t.border};
                    border-radius: 13px;
                    padding: 0 {SPACE_MD}px;
                    font-size: {FS_META}px;
                    font-weight: 600;
                }}
                QPushButton:hover {{
                    background-color: {t.border};
                    color: {t.text};
                }}
                QPushButton:checked {{
                    background-color: {t.accent};
                    color: {t.accent_fg};
                    border-color: {t.accent};
                }}
            """)
            btn.clicked.connect(lambda checked, tg=tag: self._on_item_tag_clicked(tg, checked))
            self.item_tag_bar_layout.addWidget(btn)

        self.item_tag_bar_layout.addStretch()

    def _on_item_tag_clicked(self, tag, checked):
        self._active_item_tag = tag if checked else None

        for i in range(self.item_tag_bar_layout.count()):
            w = self.item_tag_bar_layout.itemAt(i).widget()
            if w and isinstance(w, QPushButton) and w.text() != tag:
                w.setChecked(False)

        self._filter_item_rows()

    # ── saved lists ────────────────────────────────────────────── #

    def _show_saved_lists(self):
        self.left_tabs.setCurrentIndex(2)

    def _show_recipes(self):
        self.left_tabs.setCurrentIndex(0)

    def _refresh_saved_list(self):
        while self.saved_scroll_layout.count():
            child = self.saved_scroll_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        saved = get_shopping_list().get_all_lists()

        if not saved:
            empty = QLabel("No saved lists yet")
            empty.setProperty("role", "faint")
            self.saved_scroll_layout.addWidget(empty)
        else:
            for name, lid, date, *_ in saved:
                card = SavedListCard(name, lid, date, self._load_saved, self._delete_saved)
                self.saved_scroll_layout.addWidget(card)

        self.saved_scroll_layout.addStretch()

    def _load_saved(self, list_id):
        self.current_list_id = list_id
        list_data = get_shopping_list().get_list(list_id)
        if not list_data:
            return

        self.recipe_entries = list_data.get("recipe_entries", [])
        self.extra_items = list_data.get("extra_items", [])
        self.name_input.setText(list_data.get("name", ""))

        lt_missing = list_data.get("lt_missing", [])
        self.lt_have = {}
        for name in lt_missing:
            self.lt_have[name] = False

        self._refresh_cart()
        self._show_recipes()

    def _delete_saved(self, list_id):
        get_shopping_list().delete_list(list_id)
        self._refresh_saved_list()
