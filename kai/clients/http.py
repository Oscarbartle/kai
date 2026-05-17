import requests

_CF_CLIENT_ID = "9eec58e2ed475215b0d1cf5bfff9cc4d.access"
_CF_CLIENT_SECRET = "05e5c44b07bd91ad5945c5f345162c74691573ad5d82f49c1828628e61a3cb34"


def get_session() -> requests.Session:
    s = requests.Session()
    s.headers["CF-Access-Client-Id"] = _CF_CLIENT_ID
    s.headers["CF-Access-Client-Secret"] = _CF_CLIENT_SECRET
    return s


def base_url() -> str:
    from kai.core import settings
    return settings.get("api_url").rstrip("/")
