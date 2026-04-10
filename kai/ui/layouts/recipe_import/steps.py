from kai.ui import theme

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QScrollArea,
    QStackedWidget, QFrame,
)
from PySide6.QtCore import Qt


class UrlStep(QWidget):
    def __init__(self, on_submit, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        heading = QLabel("Import Recipe from URL")
        heading.setProperty("role", "heading")
        layout.addWidget(heading)

        hint = QLabel("Paste a recipe URL from a supported website.")
        hint.setProperty("role", "dim")
        layout.addWidget(hint)

        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("https://www.example.com/recipe/…")
        self.url_input.returnPressed.connect(on_submit)
        layout.addWidget(self.url_input)

        self.url_status = QLabel("")
        self.url_status.setWordWrap(True)
        layout.addWidget(self.url_status)

        layout.addStretch()


class DetailsStep(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        heading = QLabel("Review Recipe Details")
        heading.setProperty("role", "heading")
        layout.addWidget(heading)

        name_label = QLabel("Name")
        name_label.setProperty("role", "dim")
        layout.addWidget(name_label)
        self.detail_name = QLineEdit()
        layout.addWidget(self.detail_name)

        row2 = QHBoxLayout()
        row2.setSpacing(16)

        from PySide6.QtWidgets import QSpinBox, QTextEdit

        servings_col = QVBoxLayout()
        servings_col.setSpacing(4)
        servings_label = QLabel("Servings")
        servings_label.setProperty("role", "dim")
        servings_col.addWidget(servings_label)
        self.detail_servings = QSpinBox()
        self.detail_servings.setMinimum(1)
        self.detail_servings.setFixedWidth(80)
        servings_col.addWidget(self.detail_servings)
        row2.addLayout(servings_col)

        tags_col = QVBoxLayout()
        tags_col.setSpacing(4)
        tags_label = QLabel("Tags")
        tags_label.setProperty("role", "dim")
        tags_col.addWidget(tags_label)
        self.detail_tags = QLineEdit()
        self.detail_tags.setPlaceholderText("e.g. Dinner, Italian")
        tags_col.addWidget(self.detail_tags)
        row2.addLayout(tags_col, 1)

        layout.addLayout(row2)

        inst_label = QLabel("Instructions")
        inst_label.setProperty("role", "dim")
        layout.addWidget(inst_label)
        self.detail_instructions = QTextEdit()
        layout.addWidget(self.detail_instructions, 1)


class IngredientsStep(QWidget):
    def __init__(self, on_filter_change, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        header_row = QHBoxLayout()
        heading = QLabel("Match Ingredients")
        heading.setProperty("role", "heading")
        header_row.addWidget(heading, 1)

        self.ing_summary = QLabel("")
        self.ing_summary.setProperty("role", "dim")
        self.ing_summary.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        header_row.addWidget(self.ing_summary)
        layout.addLayout(header_row)

        hint = QLabel(
            "Map each scraped ingredient to an item in your pantry. "
            "Search by typing in the item box. Mark as Nominal if an exact amount doesn't matter, "
            "or Omit to exclude it from the recipe."
        )
        hint.setProperty("role", "dim")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self.ing_search = QLineEdit()
        self.ing_search.setPlaceholderText("Filter ingredients…")
        self.ing_search.setFixedHeight(32)
        self.ing_search.textChanged.connect(on_filter_change)
        layout.addWidget(self.ing_search)

        self.ing_scroll = QScrollArea()
        self.ing_scroll.setWidgetResizable(True)
        self.ing_scroll.setStyleSheet(theme.scrollbar_css())

        self.ing_container = QWidget()
        self.ing_container.setStyleSheet("background: transparent;")
        self.ing_layout = QVBoxLayout(self.ing_container)
        self.ing_layout.setContentsMargins(2, 2, 2, 2)
        self.ing_layout.setSpacing(6)

        self.ing_scroll.setWidget(self.ing_container)
        layout.addWidget(self.ing_scroll, 1)


def attach_steps_to_stack(stack: QStackedWidget, on_submit, on_filter_change):
    url_step = UrlStep(on_submit)
    details_step = DetailsStep()
    ingredients_step = IngredientsStep(on_filter_change)
    stack.addWidget(url_step)
    stack.addWidget(details_step)
    stack.addWidget(ingredients_step)
    return url_step, details_step, ingredients_step
