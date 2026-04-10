"""Woolworths NZ cart automation.

Extracts an existing browser session (via browser-cookie3) and uses the
Woolworths NZ REST API to add items to the trolley without opening a browser.

NOTE: The trolley API endpoint is reverse-engineered from browser DevTools.
      The constant TROLLEY_ADD_URL can be updated if Woolworths changes it.
"""
from __future__ import annotations

import glob
import os
from pathlib import Path

import requests as req_lib
from PySide6.QtCore import QThread, Signal

from kai.core import settings as app_settings

# ── API constants ────────────────────────────────────────────────────────────

BASE_URL = "https://www.woolworths.co.nz"
TROLLEY_ADD_URL = f"{BASE_URL}/api/v1/trolleys/my/items"

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:109.0) Gecko/20100101 Firefox/115.0",
    "Content-Type": "application/json",
    "Accept": "application/json, text/plain, */*",
    "X-Requested-With": "OnlineShopping.WebApp",
    "x-ui-ver": "7.73.30",
    "Origin": BASE_URL,
    "Referer": f"{BASE_URL}/",
}

# ── Cookie file discovery ────────────────────────────────────────────────────

_FIREFOX_PATHS = [
    # macOS
    "~/Library/Application Support/Firefox/Profiles/*/cookies.sqlite",
    # Linux
    "~/.mozilla/firefox/*/cookies.sqlite",
    # Windows
    "~/AppData/Roaming/Mozilla/Firefox/Profiles/*/cookies.sqlite",
]

_CHROME_PATHS = [
    # macOS
    "~/Library/Application Support/Google/Chrome/Default/Cookies",
    # Linux
    "~/.config/google-chrome/Default/Cookies",
    # Windows
    "~/AppData/Local/Google/Chrome/User Data/Default/Cookies",
]

_BRAVE_PATHS = [
    # macOS
    "~/Library/Application Support/BraveSoftware/Brave-Browser/Default/Cookies",
    # Linux
    "~/.config/BraveSoftware/Brave-Browser/Default/Cookies",
    # Windows
    "~/AppData/Local/BraveSoftware/Brave-Browser/User Data/Default/Cookies",
]

_EDGE_PATHS = [
    # macOS
    "~/Library/Application Support/Microsoft Edge/Default/Cookies",
    # Linux
    "~/.config/microsoft-edge/Default/Cookies",
    # Windows
    "~/AppData/Local/Microsoft/Edge/User Data/Default/Cookies",
]

_CHROMIUM_PATHS = [
    # macOS
    "~/Library/Application Support/Chromium/Default/Cookies",
    # Linux
    "~/.config/chromium/Default/Cookies",
    # Windows
    "~/AppData/Local/Chromium/User Data/Default/Cookies",
]

_BROWSER_PATHS: dict[str, list[str]] = {
    "firefox": _FIREFOX_PATHS,
    "chrome": _CHROME_PATHS,
    "brave": _BRAVE_PATHS,
    "edge": _EDGE_PATHS,
    "chromium": _CHROMIUM_PATHS,
}


def _find_cookie_file(browser: str) -> str | None:
    patterns = _BROWSER_PATHS.get(browser, [])
    for pattern in patterns:
        matches = glob.glob(os.path.expanduser(pattern))
        if matches:
            # prefer the most recently modified profile
            return max(matches, key=os.path.getmtime)
    return None


# ── Session creation ─────────────────────────────────────────────────────────

def _is_firefox_based(browser: str) -> bool:
    return browser == "firefox"


def get_session(browser: str | None = None) -> req_lib.Session | None:
    """Build a requests.Session loaded with the user's browser cookies for Woolworths NZ.

    Returns None if the cookie file cannot be found.
    """
    import browser_cookie3

    if browser is None:
        browser = app_settings.get("browser") or "firefox"

    cookie_file = _find_cookie_file(browser)
    if cookie_file is None:
        return None

    try:
        if _is_firefox_based(browser):
            jar = browser_cookie3.firefox(
                cookie_file=cookie_file,
                domain_name=".woolworths.co.nz",
            )
        else:
            jar = browser_cookie3.chrome(
                cookie_file=cookie_file,
                domain_name=".woolworths.co.nz",
            )
    except Exception:
        return None

    session = req_lib.Session()
    session.cookies.update(jar)
    session.headers.update(_HEADERS)
    return session


# ── Auth check ───────────────────────────────────────────────────────────────

# Cookies that are only present when the user is logged in to Woolworths NZ
_AUTH_COOKIE_INDICATORS = {
    "KEYCLOAK_IDENTITY",       # Keycloak auth token
    "KEYCLOAK_IDENTITY_LEGACY",
    "KC_AUTH_STATE",
    "ASP.NET_SessionId",       # ASP.NET backend session
}


def check_auth(session: req_lib.Session) -> bool:
    """Return True if the session has a valid Woolworths login (cookie-based check)."""
    cookie_names = {c.name for c in session.cookies}
    return bool(cookie_names & _AUTH_COOKIE_INDICATORS)


# ── Cart mutation ────────────────────────────────────────────────────────────

def add_item_to_trolley(session: req_lib.Session, stock_code: str, qty: int) -> bool:
    """POST one item to the Woolworths trolley. Returns True on success."""
    # Set XSRF token header from cookie if present
    xsrf = next((c.value for c in session.cookies if c.name == "XSRF-TOKEN"), None)
    headers = {"X-XSRF-TOKEN": xsrf} if xsrf else {}
    payload = {
        "sku": str(stock_code),
        "quantity": qty,
        "pricingUnit": "Each",
    }
    try:
        r = session.post(TROLLEY_ADD_URL, json=payload, headers=headers, timeout=10)
        if r.status_code not in (200, 201):
            return False
        return r.json().get("isSuccessful", False)
    except Exception:
        return False


# ── Background worker ────────────────────────────────────────────────────────

_active_cart_threads: list[QThread] = []


class _CartWorker(QThread):
    item_done = Signal(str, bool)   # (item_name, success)
    auth_failed = Signal()
    finished_adding = Signal(int, int)  # (ok_count, fail_count)

    def __init__(self, items: list[dict]):
        """items: list of {name, stock_code, qty}"""
        super().__init__()
        self._items = items

    def run(self):
        browser = app_settings.get("browser") or "firefox"
        session = get_session(browser)

        if session is None or not check_auth(session):
            self.auth_failed.emit()
            return

        ok = 0
        fail = 0
        for item in self._items:
            success = add_item_to_trolley(session, item["stock_code"], item["qty"])
            self.item_done.emit(item["name"], success)
            if success:
                ok += 1
            else:
                fail += 1

        self.finished_adding.emit(ok, fail)


def start_cart_worker(
    items: list[dict],
    on_item_done=None,
    on_auth_failed=None,
    on_finished=None,
) -> _CartWorker:
    """Spawn a background cart worker and return it.

    items: list of {name, stock_code, qty}
    """
    worker = _CartWorker(items)

    if on_item_done:
        worker.item_done.connect(on_item_done)
    if on_auth_failed:
        worker.auth_failed.connect(on_auth_failed)
    if on_finished:
        worker.finished_adding.connect(on_finished)

    def _cleanup():
        if worker in _active_cart_threads:
            _active_cart_threads.remove(worker)

    worker.finished_adding.connect(_cleanup)
    worker.auth_failed.connect(_cleanup)
    _active_cart_threads.append(worker)
    worker.start()
    return worker
