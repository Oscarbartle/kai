import os
from pathlib import Path
from kai.core.io import IO


# Settings file always lives alongside the app (never on the remote share)
_LOCAL_DATA_DIR = Path(os.path.join(os.path.dirname(__file__), "../../data")).resolve()
_json_path = _LOCAL_DATA_DIR / "settings.json"
_io = IO(_json_path)

DEFAULTS = {
    "price_display_mode": "per_unit",       # "per_unit" or "per_weight"
    "data_dir": "",                          # empty ⇒ use local data/
    "browser": "firefox",                    # browser for Woolworths cart: zen, firefox, chrome, edge, brave, chromium
    "price_history_window_days": 30,         # N-day low flag window
}


def get(key: str):
    val = _io.get(key)
    if val is None:
        return DEFAULTS.get(key)
    return val


def set(key: str, value) -> None:
    _io.create(key, value, overwrite=True)


def data_dir() -> Path:
    """Return the active data directory (local default or user-configured path)."""
    custom = get("data_dir")
    if custom:
        return Path(custom)
    return _LOCAL_DATA_DIR
