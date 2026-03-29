from kai.ui.layouts.recipes_add import RecipesAdd
from kai.ui.layouts.recipe_import import RecipeImport
from kai.ui.layouts.tags import Tags
from kai.ui.layouts.recipes_viewer import RecipesViewer
from kai.ui import theme

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QStyle, QStyleOption, QDialog
)
from PySide6.QtGui import QPainter


class RecipesPage(QWidget):
    def __init__(self, state):
        super().__init__()

        self.state = state

        self.layout = QGridLayout()
        self.layout.setContentsMargins(8, 8, 8, 8)
        self.layout.setSpacing(8)
        self.layout.setColumnStretch(0, 1)
        self.layout.setColumnStretch(1, 3)
        self.setLayout(self.layout)

        self.add_widgets()

    def paintEvent(self, event):
        opt = QStyleOption()
        opt.initFrom(self)
        p = QPainter(self)
        self.style().drawPrimitive(QStyle.PE_Widget, opt, p, self)

    def add_widgets(self):
        self.tags = Tags(self.state, source="recipes")
        self.tags.setObjectName("page_panel")
        self.layout.addWidget(self.tags, 0, 0)

        self.recipes_viewer = RecipesViewer(self.state)
        self.recipes_viewer.setObjectName("page_panel")
        self.recipes_viewer.add_button.clicked.connect(self._open_add_dialog)
        self.recipes_viewer.import_button.clicked.connect(self._open_import_dialog)
        self.layout.addWidget(self.recipes_viewer, 0, 1)

    def _open_add_dialog(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("New Recipe")
        dialog.setMinimumSize(720, 520)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(0, 0, 0, 0)

        recipes_add = RecipesAdd(self.state)
        layout.addWidget(recipes_add)

        dialog.exec()

    def _open_import_dialog(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Import Recipe")
        dialog.setMinimumSize(780, 580)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(0, 0, 0, 0)

        recipe_import = RecipeImport(self.state)
        layout.addWidget(recipe_import)

        dialog.exec()
