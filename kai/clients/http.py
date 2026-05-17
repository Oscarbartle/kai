import os
import requests


def get_session() -> requests.Session:
    s = requests.Session()
    cid = os.environ.get("KAI_CF_CLIENT_ID", "")
    csecret = os.environ.get("KAI_CF_CLIENT_SECRET", "")
    if cid:
        s.headers["CF-Access-Client-Id"] = cid
    if csecret:
        s.headers["CF-Access-Client-Secret"] = csecret
    return s


def base_url() -> str:
    from kai.core import settings
    url = os.environ.get("KAI_API_URL") or settings.get("api_url") or "http://localhost:8000"
    return url.rstrip("/")
