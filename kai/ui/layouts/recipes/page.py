from kai.ui.layouts.recipes_add.page import RecipesAdd
from kai.ui.layouts.recipe_import.page import RecipeImport
from kai.ui.layouts.tags import Tags
from kai.ui.layouts.recipes.viewer import RecipesViewer
from kai.ui import theme

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QStyle, QStyleOption, QDialog
)
from PySide6.QtGui import QPainter
from PySide6.QtCore import Qt


class RecipesPage(QWidget):
    def __init__(self, state):
        super().__init__()

        self.state = state

        outer = QHBoxLayout()
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(0)
        self.setLayout(outer)

        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setChildrenCollapsible(False)
        self.splitter.setHandleWidth(6)
        outer.addWidget(self.splitter)

        self.add_widgets()

    def paintEvent(self, event):
        opt = QStyleOption()
        opt.initFrom(self)
        p = QPainter(self)
        self.style().drawPrimitive(QStyle.PE_Widget, opt, p, self)

    def add_widgets(self):
        self.tags = Tags(self.state, source="recipes")
        self.tags.setObjectName("page_panel")
        self.splitter.addWidget(self.tags)

        self.recipes_viewer = RecipesViewer(self.state)
        self.recipes_viewer.setObjectName("page_panel")
        self.recipes_viewer.add_button.clicked.connect(self._open_add_dialog)
        self.recipes_viewer.import_button.clicked.connect(self._open_import_dialog)
        self.splitter.addWidget(self.recipes_viewer)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 3)

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
