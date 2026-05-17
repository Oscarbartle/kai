"""Design tokens for Kai's UI.

Import these constants wherever pixel values are needed — never hard-code
spacing, radii, or font sizes directly in widget files.
"""

# ── Spacing (4px grid) ───────────────────────────────────────────────
SPACE_XS = 4
SPACE_SM = 8
SPACE_MD = 16
SPACE_LG = 24
SPACE_XL = 40

# ── Radii ────────────────────────────────────────────────────────────
RADIUS_SM = 6    # inputs, chips, small buttons
RADIUS_MD = 10   # cards, panels, dialogs
RADIUS_LG = 14   # featured / large cards

# ── Borders ──────────────────────────────────────────────────────────
BORDER_W = 1

# ── Control heights ──────────────────────────────────────────────────
H_INPUT    = 32
H_BTN_SM   = 11
H_BTN_MD   = 13
H_ICON_BTN = 11   # square icon buttons

# ── Card heights ─────────────────────────────────────────────────────
H_ROW     = 40   # shopping item row
H_CARD    = 68   # recipe / item detail card
H_FEATURE = 92   # featured card (recipe picker)

# ── Typography — sizes ───────────────────────────────────────────────
FS_TITLE   = 22
FS_HEADING = 15
FS_BODY    = 13
FS_META    = 11  # secondary / muted text (was 10/11/12 in various places)
FS_TINY    = 10  # badges only

# ── Typography — weights ─────────────────────────────────────────────
FW_BODY   = 400
FW_MEDIUM = 600
FW_BOLD   = 700
