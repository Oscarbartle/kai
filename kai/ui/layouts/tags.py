from kai.objects.item import Item
from kai.objects.recipe import Recipe
from ..widgets.list_box import ListBox
from kai.ui import theme

from PySide6.QtWidgets import QLabel, QWidget, QVBoxLayout, QStyle, QStyleOption
from PySide6.QtGui import QPainter

class Tags(QWidget):
    def __init__(self, state, source="items"):
        super().__init__()

        self.state = state
        self.source = source

        self.layout = QVBoxLayout()
        self.layout.setContentsMargins(12, 12, 12, 12)
        self.layout.setSpacing(8)
        self.setLayout(self.layout)

        self.create_widgets()
        self.add_layouts()
        self.connections()

    def paintEvent(self, event):
        opt = QStyleOption()
        opt.initFrom(self)
        p = QPainter(self)
        self.style().drawPrimitive(QStyle.PE_Widget, opt, p, self)

    def create_widgets(self):
        self.tags_label = QLabel("Tags")
        self.tags_label.setProperty("role", "heading")

        self.tags_list = ListBox(searchable=True)
        self._reload_tags()

    def _reload_tags(self):
        if self.source == "recipes":
            tags = Recipe().get_recipe_tags()
        else:
            tags = Item().get_item_tags()

        default = ["All"]
        if self.source == "recipes":
            default.append("★ Favourites")
        default.extend(sorted(tags))
        self.tags_list.add_items(default)

    def add_layouts(self):
        self.layout.addWidget(self.tags_label)
        self.layout.addWidget(self.tags_list)

    def connections(self):
        self.tags_list.list_widget.currentTextChanged.connect(self._on_tag_clicked)
        self.state.new_items.connect(self._reload_tags)
        self.state.new_recipes.connect(self._reload_tags)

    def _on_tag_clicked(self, tag: str):
        if tag:
            self.state.select_tag(tag)
