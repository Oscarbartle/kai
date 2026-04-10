"""
Centralized theme system for Kai.

Every UI file imports colors and stylesheet fragments from here.
Call `set_theme("ocean")` before building the UI to pick a palette.
The global stylesheet is applied once in main.py via `global_stylesheet()`.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
import json
import sys


def _platform_font() -> str:
    """Return a CSS font-family string with only fonts that exist on this OS."""
    if sys.platform == "darwin":
        return '".AppleSystemUIFont", "Helvetica Neue"'
    if sys.platform == "win32":
        return '"Segoe UI", "Arial"'
    # Linux / other
    return '"Ubuntu", "Noto Sans", "DejaVu Sans", "Arial"'


# ── colour palettes ──────────────────────────────────────────────── #

@dataclass(frozen=True)
class Palette:
    name: str

    # surfaces (darkest → lightest)
    bg:        str  # window / deepest background
    surface:   str  # sidebar, page panels
    card:      str  # elevated cards, inputs
    border:    str  # subtle separators

    # text
    text:      str  # primary text
    text_dim:  str  # secondary / muted
    text_faint: str  # placeholders, disabled

    # accents
    accent:    str  # primary brand colour (buttons, active states)
    accent_fg: str  # text on accent backgrounds
    success:   str  # green highlights (specials, positive)
    danger:    str  # red highlights (delete, warnings)

    # optional accents
    warning:   str = ""  # orange highlights (long-term specials)

    # buttons (separate from accent so users can customise independently)
    btn_bg:    str = ""
    btn_fg:    str = ""
    btn_hover: str = ""
    btn_pressed: str = ""

    # list highlight
    list_hl:    str = ""   # selected-item background tint
    list_hl_fg: str = ""   # selected-item text

    # scrollbar
    scroll:    str = ""
    scroll_hover: str = ""

    def __post_init__(self):
        if not self.warning:
            object.__setattr__(self, "warning", "#d4a247")
        if not self.btn_bg:
            object.__setattr__(self, "btn_bg", self.accent)
        if not self.btn_fg:
            object.__setattr__(self, "btn_fg", self.accent_fg)
        if not self.btn_hover:
            object.__setattr__(self, "btn_hover", f"{self.btn_bg}cc")
        if not self.btn_pressed:
            object.__setattr__(self, "btn_pressed", f"{self.btn_bg}99")
        if not self.list_hl:
            object.__setattr__(self, "list_hl", f"{self.accent}33")
        if not self.list_hl_fg:
            object.__setattr__(self, "list_hl_fg", self.accent)
        if not self.scroll:
            object.__setattr__(self, "scroll", self.text_dim)
        if not self.scroll_hover:
            object.__setattr__(self, "scroll_hover", self.text)


PALETTES: dict[str, Palette] = {
    "graphite": Palette(
        name="graphite",
        bg="#1a1a1e",
        surface="#222226",
        card="#2a2a2f",
        border="#36363d",
        text="#d8d8dc",
        text_dim="#8e8e96",
        text_faint="#5c5c64",
        accent="#7c9aaf",
        accent_fg="#1a1a1e",
        success="#7db88a",
        warning="#d4a247",
        danger="#c97070",
    ),
    "slate": Palette(
        name="slate",
        bg="#181c22",
        surface="#1f2329",
        card="#262b33",
        border="#323840",
        text="#cdd4de",
        text_dim="#7d8694",
        text_faint="#505962",
        accent="#6ba3c4",
        accent_fg="#181c22",
        success="#82b892",
        warning="#d4a85a",
        danger="#c47878",
    ),
    "moss": Palette(
        name="moss",
        bg="#191c19",
        surface="#21241f",
        card="#292d27",
        border="#363b34",
        text="#d4d8d0",
        text_dim="#8a8f82",
        text_faint="#585e52",
        accent="#8aab7c",
        accent_fg="#191c19",
        success="#8ab88a",
        warning="#c8a350",
        danger="#c48070",
    ),
    "dusk": Palette(
        name="dusk",
        bg="#1c1921",
        surface="#232028",
        card="#2b2830",
        border="#3a3640",
        text="#d6d2dc",
        text_dim="#8c8696",
        text_faint="#5e5868",
        accent="#a08cb8",
        accent_fg="#1c1921",
        success="#88b88a",
        warning="#d0a050",
        danger="#c47878",
    ),
}

# ── active palette ───────────────────────────────────────────────── #

_active: Palette = PALETTES["graphite"]

def _get_data_dir() -> Path:
    from kai.core import settings as _s
    return _s.data_dir()

_data_dir = _get_data_dir()
_custom_path = _data_dir / "custom_themes.json"
_pref_path = _data_dir / "theme_pref.json"


def _load_custom_palettes():
    if _custom_path.exists():
        with _custom_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        for name, colors in data.items():
            PALETTES[name] = Palette(**colors)

_load_custom_palettes()


def _load_saved_theme():
    """Restore the last-used theme on startup."""
    global _active
    if _pref_path.exists():
        with _pref_path.open("r", encoding="utf-8") as f:
            name = json.load(f).get("theme", "graphite")
        _active = PALETTES.get(name, PALETTES["graphite"])

_load_saved_theme()


def save_theme_pref():
    """Persist the current theme name so it survives restarts."""
    _data_dir.mkdir(parents=True, exist_ok=True)
    with _pref_path.open("w", encoding="utf-8") as f:
        json.dump({"theme": _active.name}, f)


def save_custom_palette(palette: Palette):
    data: dict[str, dict] = {}
    if _custom_path.exists():
        with _custom_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    data[palette.name] = {
        "name": palette.name,
        "bg": palette.bg, "surface": palette.surface, "card": palette.card,
        "border": palette.border, "text": palette.text, "text_dim": palette.text_dim,
        "text_faint": palette.text_faint, "accent": palette.accent,
        "accent_fg": palette.accent_fg, "success": palette.success,
        "danger": palette.danger, "warning": palette.warning,
        "btn_bg": palette.btn_bg,
        "btn_fg": palette.btn_fg, "btn_hover": palette.btn_hover,
        "btn_pressed": palette.btn_pressed,
        "list_hl": palette.list_hl,
        "list_hl_fg": palette.list_hl_fg, "scroll": palette.scroll,
        "scroll_hover": palette.scroll_hover,
    }
    _custom_path.parent.mkdir(parents=True, exist_ok=True)
    with _custom_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)
    PALETTES[palette.name] = palette


def delete_custom_palette(name: str):
    if _custom_path.exists():
        with _custom_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        data.pop(name, None)
        with _custom_path.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
    PALETTES.pop(name, None)


def is_builtin(name: str) -> bool:
    return name in ("graphite", "slate", "moss", "dusk")


def set_theme(name: str):
    global _active
    _active = PALETTES.get(name, PALETTES["graphite"])
    save_theme_pref()


def theme() -> Palette:
    return _active


def theme_names() -> list[str]:
    return list(PALETTES.keys())


# ── reusable stylesheet fragments ────────────────────────────────── #

def scrollbar_css(width: int = 6) -> str:
    t = theme()
    return f"""
        QScrollBar:vertical {{
            background: transparent;
            width: {width}px;
            border: none;
            border-radius: {width // 2}px;
        }}
        QScrollBar::handle:vertical {{
            background: {t.scroll};
            border-radius: {width // 2}px;
            min-height: 24px;
        }}
        QScrollBar::handle:vertical:hover {{
            background: {t.scroll_hover};
        }}
        QScrollBar::add-line:vertical,
        QScrollBar::sub-line:vertical {{
            height: 0px;
        }}
        QScrollBar::add-page:vertical,
        QScrollBar::sub-page:vertical {{
            background: transparent;
        }}
        QScrollBar:horizontal {{
            height: 0px;
        }}
    """


def card_css(object_name: str, *, radius: int = 10, border: bool = True) -> str:
    t = theme()
    border_line = f"border: 1px solid {t.border};" if border else "border: none;"
    return f"""
        QWidget#{object_name} {{
            background-color: {t.card};
            border-radius: {radius}px;
            {border_line}
        }}
    """


def button_css(*, primary: bool = False) -> str:
    t = theme()
    if primary:
        return f"""
            QPushButton {{
                background-color: {t.btn_bg};
                color: {t.btn_fg};
                border: none;
                border-radius: 8px;
                padding: 10px 20px;
                font-size: 13px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {t.btn_hover};
            }}
            QPushButton:pressed {{
                background-color: {t.btn_pressed};
            }}
        """
    return f"""
        QPushButton {{
            background-color: {t.card};
            color: {t.text};
            border: 1px solid {t.border};
            border-radius: 8px;
            padding: 8px 16px;
            font-size: 12px;
            font-weight: 600;
        }}
        QPushButton:hover {{
            background-color: {t.border};
            color: {t.text};
        }}
    """


def input_css() -> str:
    t = theme()
    return f"""
        QLineEdit, QSpinBox, QComboBox {{
            background-color: {t.bg};
            color: {t.text};
            border: 1px solid {t.border};
            border-radius: 6px;
            padding: 7px 10px;
            font-size: 12px;
            selection-background-color: {t.accent};
        }}
        QLineEdit:focus, QSpinBox:focus, QComboBox:focus {{
            border: 1px solid {t.accent};
        }}
        QLineEdit::placeholder {{
            color: {t.text_faint};
        }}
        QComboBox::drop-down {{
            border: none;
            width: 24px;
        }}
        QComboBox QAbstractItemView {{
            background-color: {t.card};
            color: {t.text};
            border: 1px solid {t.border};
            selection-background-color: {t.accent};
            selection-color: {t.accent_fg};
        }}
        QTextEdit {{
            background-color: {t.bg};
            color: {t.text};
            border: 1px solid {t.border};
            border-radius: 6px;
            padding: 6px;
            font-size: 12px;
            selection-background-color: {t.accent};
        }}
        QTextEdit:focus {{
            border: 1px solid {t.accent};
        }}
    """


def checkbox_css() -> str:
    t = theme()
    return f"""
        QCheckBox {{
            color: {t.text_dim};
            spacing: 6px;
            font-size: 12px;
        }}
        QCheckBox::indicator {{
            width: 16px;
            height: 16px;
            border-radius: 4px;
            border: 1px solid {t.border};
            background: {t.bg};
        }}
        QCheckBox::indicator:checked {{
            background: {t.accent};
            border: 1px solid {t.accent};
        }}
    """


def list_widget_css() -> str:
    t = theme()
    return f"""
        QListWidget {{
            background-color: {t.bg};
            border: 1px solid {t.border};
            border-radius: 8px;
            color: {t.text};
            font-size: 12px;
            padding: 4px;
            outline: none;
        }}
        QListWidget::item {{
            padding: 5px 8px;
            border-radius: 6px;
        }}
        QListWidget::item:selected {{
            background-color: {t.list_hl};
            color: {t.list_hl_fg};
        }}
        QListWidget::item:hover:!selected {{
            background-color: {t.border}66;
        }}
        {scrollbar_css(4)}
    """


def tab_widget_css() -> str:
    """Inner tab widget styling (e.g. recipe form tabs)."""
    t = theme()
    return f"""
        QTabWidget::pane {{
            border: 1px solid {t.border};
            border-radius: 8px;
            background: transparent;
        }}
        QTabBar::tab {{
            background: {t.bg};
            color: {t.text_dim};
            border: 1px solid {t.border};
            border-bottom: none;
            padding: 7px 18px;
            font-size: 12px;
            font-weight: 600;
            border-top-left-radius: 8px;
            border-top-right-radius: 8px;
            margin-right: 2px;
        }}
        QTabBar::tab:selected {{
            background: {t.card};
            color: {t.text};
        }}
        QTabBar::tab:hover:!selected {{
            background: {t.surface};
            color: {t.text};
        }}
    """


def page_tab_css() -> str:
    """Top-position page-level tab styling, left-aligned."""
    t = theme()
    return f"""
        QTabWidget::pane {{
            border: none;
            background: transparent;
        }}
        QTabWidget::tab-bar {{
            left: 0px;
        }}
        QTabBar {{
            background: {t.bg};
        }}
        QTabBar::tab {{
            background: transparent;
            color: {t.text_dim};
            border: none;
            border-bottom: 3px solid transparent;
            padding: 10px 24px;
            font-size: 12px;
            font-weight: bold;
            min-width: 100px;
        }}
        QTabBar::tab:selected {{
            background: {t.surface};
            color: {t.text};
            border-bottom: 3px solid {t.accent};
        }}
        QTabBar::tab:hover:!selected {{
            background: {t.card};
            color: {t.text};
        }}
    """


def label_css(role: str = "body") -> str:
    t = theme()
    styles = {
        "heading":  f"color: {t.text}; font-size: 15px; font-weight: bold;",
        "body":     f"color: {t.text}; font-size: 12px;",
        "dim":      f"color: {t.text_dim}; font-size: 11px;",
        "faint":    f"color: {t.text_faint}; font-size: 10px;",
        "accent":   f"color: {t.accent}; font-size: 13px; font-weight: bold;",
        "price":    f"color: {t.accent}; font-size: 14px; font-weight: bold;",
        "success":  f"color: {t.success}; font-size: 14px; font-weight: bold;",
        "danger":   f"color: {t.danger}; font-size: 12px;",
    }
    return styles.get(role, styles["body"])


# ── new reusable fragments ────────────────────────────────────────── #

def section_label_css() -> str:
    """CSS for section header labels (uppercase, letter-spaced)."""
    t = theme()
    return (
        f"color: {t.text_dim}; font-size: 10px; font-weight: 700; "
        "letter-spacing: 0.8px; text-transform: uppercase;"
    )


def divider_line_css() -> str:
    """CSS for a 1-pixel horizontal QFrame divider."""
    t = theme()
    return f"background: {t.border}; border: none; max-height: 1px;"


def inline_card_css(object_name: str, *, radius: int = 10) -> str:
    """CSS for an inline card panel widget (card bg + border)."""
    t = theme()
    return f"""
        QWidget#{object_name} {{
            background-color: {t.card};
            border: 1px solid {t.border};
            border-radius: {radius}px;
        }}
    """


def surface_row_css(object_name: str, *, radius: int = 6) -> str:
    """CSS for a surface-coloured row widget (lighter than card)."""
    t = theme()
    return f"""
        QWidget#{object_name} {{
            background-color: {t.surface};
            border-radius: {radius}px;
            border: 1px solid {t.border};
        }}
    """


def delete_btn_css(*, font_size: int = 13) -> str:
    """CSS for a small × delete button — danger colour and bg on hover."""
    t = theme()
    return f"""
        QPushButton {{
            background: transparent;
            color: {t.text_faint};
            border: none;
            font-size: {font_size}px;
            font-weight: bold;
        }}
        QPushButton:hover {{
            color: {t.danger};
            background: {t.danger}22;
            border-radius: 4px;
        }}
    """


def remove_btn_css(*, font_size: int = 11) -> str:
    """CSS for a tiny × chip-remove button — only danger text on hover."""
    t = theme()
    return f"""
        QPushButton {{
            background: transparent;
            color: {t.text_faint};
            border: none;
            font-size: {font_size}px;
        }}
        QPushButton:hover {{ color: {t.danger}; }}
    """


def icon_btn_css(color: str | None = None) -> str:
    """CSS for a ghost icon button (refresh, fav) — accent on hover."""
    t = theme()
    fg = color if color is not None else t.text_faint
    return f"""
        QPushButton {{
            background: transparent;
            color: {fg};
            border: none;
            font-size: 14px;
            font-weight: bold;
            border-radius: 4px;
        }}
        QPushButton:hover {{
            background: {t.accent}22;
            color: {t.accent};
        }}
    """


def badge_css(bg: str, fg: str) -> str:
    """CSS for a round count QLabel badge."""
    return f"""
        background-color: {bg};
        color: {fg};
        border-radius: 11px;
        font-size: 11px;
        font-weight: bold;
    """


def mini_primary_btn_css(*, radius: int = 6, font_size: int = 13) -> str:
    """CSS for a compact primary action button (e.g. Add)."""
    t = theme()
    return f"""
        QPushButton {{
            background-color: {t.btn_bg};
            color: {t.btn_fg};
            border: none;
            border-radius: {radius}px;
            font-size: {font_size}px;
            font-weight: bold;
        }}
        QPushButton:hover {{ background-color: {t.btn_hover}; }}
        QPushButton:pressed {{ background-color: {t.btn_pressed}; }}
    """


def collapsible_btn_css() -> str:
    """CSS for a collapsible section toggle button."""
    t = theme()
    return f"""
        QPushButton {{
            background-color: {t.surface};
            color: {t.text};
            border: none;
            border-radius: 6px;
            font-size: 12px;
            font-weight: bold;
            text-align: left;
            padding-left: 4px;
        }}
        QPushButton:hover {{ background-color: {t.border}; }}
    """


def context_menu_css() -> str:
    """CSS for a QMenu context menu."""
    t = theme()
    return (
        f"QMenu {{ background: {t.surface}; color: {t.text}; "
        f"border: 1px solid {t.border}; padding: 4px; }}"
        f"QMenu::item {{ padding: 6px 24px 6px 12px; border-radius: 4px; }}"
        f"QMenu::item:selected {{ background: {t.accent}; color: {t.accent_fg}; }}"
    )


def tag_pill_label_css(*, font_size: int = 9) -> str:
    """CSS for a non-interactive inline tag label pill (QLabel)."""
    t = theme()
    return f"""
        background-color: {t.surface};
        color: {t.text_dim};
        border: 1px solid {t.border};
        border-radius: 8px;
        padding: 1px 6px;
        font-size: {font_size}px;
    """


# ── global stylesheet (applied once on QMainWindow) ──────────────── #

def _gs_base(t) -> str:
    return f"""
        QMainWindow {{
            background-color: {t.bg};
        }}
        QWidget {{
            font-family: {_platform_font()};
        }}
        QLabel {{
            color: {t.text};
            background: transparent;
        }}
        QToolTip {{
            background-color: {t.card};
            color: {t.text};
            border: 1px solid {t.border};
            border-radius: 6px;
            padding: 6px 8px;
            font-size: 11px;
        }}
    """


def _gs_layout(t) -> str:
    return f"""
        QWidget#sidebar {{
            background-color: {t.surface};
            border-right: 1px solid {t.border};
        }}
        QWidget#page_panel {{
            background-color: {t.surface};
            border-radius: 10px;
            border: 1px solid {t.border};
        }}
    """


def _gs_label_roles(t) -> str:
    return f"""
        QLabel[role="heading"] {{
            color: {t.text};
            font-size: 15px;
            font-weight: bold;
        }}
        QLabel[role="body"] {{
            color: {t.text};
            font-size: 12px;
        }}
        QLabel[role="dim"] {{
            color: {t.text_dim};
            font-size: 11px;
        }}
        QLabel[role="faint"] {{
            color: {t.text_faint};
            font-size: 10px;
        }}
        QLabel[role="accent"] {{
            color: {t.accent};
            font-size: 13px;
            font-weight: bold;
        }}
        QLabel[role="price"] {{
            color: {t.accent};
            font-size: 14px;
            font-weight: bold;
        }}
        QLabel[role="success"] {{
            color: {t.success};
            font-size: 14px;
            font-weight: bold;
        }}
        QLabel[role="danger"] {{
            color: {t.danger};
            font-size: 12px;
        }}
        QLabel[role="title"] {{
            color: {t.accent};
            font-size: 22px;
            font-weight: bold;
            padding: 4px 8px 16px 8px;
        }}
    """


def _gs_buttons(t) -> str:
    return f"""
        QPushButton[btn="primary"] {{
            background-color: {t.btn_bg};
            color: {t.btn_fg};
            border: none;
            border-radius: 8px;
            padding: 10px 20px;
            font-size: 13px;
            font-weight: bold;
        }}
        QPushButton[btn="primary"]:hover {{
            background-color: {t.btn_hover};
        }}
        QPushButton[btn="primary"]:pressed {{
            background-color: {t.btn_pressed};
        }}
        QPushButton[btn="secondary"] {{
            background-color: {t.card};
            color: {t.text};
            border: 1px solid {t.border};
            border-radius: 8px;
            padding: 8px 16px;
            font-size: 12px;
            font-weight: 600;
        }}
        QPushButton[btn="secondary"]:hover {{
            background-color: {t.border};
            color: {t.text};
        }}
    """


def _gs_list_widget(t) -> str:
    return f"""
        QListWidget {{
            background-color: {t.bg};
            border: 1px solid {t.border};
            border-radius: 8px;
            color: {t.text};
            font-size: 12px;
            padding: 4px;
            outline: none;
        }}
        QListWidget::item {{
            padding: 5px 8px;
            border-radius: 6px;
        }}
        QListWidget::item:selected {{
            background-color: {t.list_hl};
            color: {t.list_hl_fg};
        }}
        QListWidget::item:hover:!selected {{
            background-color: {t.border}66;
        }}
    """


def _gs_tabs(t) -> str:
    return f"""
        QTabWidget[tab="page"]::pane {{
            border: none;
            background: transparent;
        }}
        QTabWidget[tab="page"]::tab-bar {{
            left: 0px;
        }}
        QTabWidget[tab="page"] QTabBar {{
            background: {t.bg};
        }}
        QTabWidget[tab="page"] QTabBar::tab {{
            background: transparent;
            color: {t.text_dim};
            border: none;
            border-bottom: 3px solid transparent;
            padding: 10px 24px;
            font-size: 12px;
            font-weight: bold;
            min-width: 100px;
        }}
        QTabWidget[tab="page"] QTabBar::tab:selected {{
            background: {t.surface};
            color: {t.text};
            border-bottom: 3px solid {t.accent};
        }}
        QTabWidget[tab="page"] QTabBar::tab:hover:!selected {{
            background: {t.card};
            color: {t.text};
        }}
        QTabWidget[tab="inner"]::pane {{
            border: 1px solid {t.border};
            border-radius: 8px;
            background: transparent;
        }}
        QTabWidget[tab="inner"] QTabBar::tab {{
            background: {t.bg};
            color: {t.text_dim};
            border: 1px solid {t.border};
            border-bottom: none;
            padding: 7px 24px;
            min-width: 80px;
            font-size: 12px;
            font-weight: 600;
            border-top-left-radius: 8px;
            border-top-right-radius: 8px;
            margin-right: 2px;
        }}
        QTabWidget[tab="inner"] QTabBar::tab:selected {{
            background: {t.card};
            color: {t.text};
        }}
        QTabWidget[tab="inner"] QTabBar::tab:hover:!selected {{
            background: {t.surface};
            color: {t.text};
        }}
    """


def _gs_scroll_area() -> str:
    return """
        QScrollArea {
            background: transparent;
            border: none;
        }
    """


def _gs_chips(t) -> str:
    return f"""
        QPushButton[btn="chip"] {{
            background: {t.card};
            color: {t.text_dim};
            border: 1px solid {t.border};
            border-radius: 13px;
            padding: 2px 12px;
            font-size: 11px;
        }}
        QPushButton[btn="chip"]:hover {{
            background: {t.list_hl};
            color: {t.list_hl_fg};
            border-color: {t.list_hl_fg};
        }}
    """


def _gs_dialog(t) -> str:
    return f"""
        QDialog {{
            background-color: {t.surface};
            border: 1px solid {t.border};
        }}
    """


def global_stylesheet() -> str:
    t = theme()
    return (
        _gs_base(t)
        + input_css()
        + checkbox_css()
        + scrollbar_css()
        + _gs_layout(t)
        + _gs_label_roles(t)
        + _gs_buttons(t)
        + _gs_list_widget(t)
        + _gs_tabs(t)
        + _gs_scroll_area()
        + _gs_chips(t)
        + _gs_dialog(t)
    )
