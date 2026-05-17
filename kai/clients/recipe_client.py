"""HTTP client for the /recipes API endpoints."""
from __future__ import annotations

from kai.clients.http import get_session, base_url


class RecipeClient:
    _shared_cache: dict | None = None       # class-level: shared across all instances
    _scaled_cache: dict = {}                # (rid, multiplier) → scaled ingredients

    def __init__(self):
        self.io = self._IoProxy(self)

    # ── cache ─────────────────────────────────────────────────────── #

    def _fetch_all(self) -> dict:
        """GET /recipes and return {id: recipe_dict} (etag stripped from values)."""
        s = get_session()
        r = s.get(f"{base_url()}/recipes")
        r.raise_for_status()
        result = {}
        for item in r.json():
            rid = item["id"]
            doc = {k: v for k, v in item.items() if k not in ("id", "etag")}
            result[rid] = doc
        return result

    def _get_cache(self) -> dict:
        if RecipeClient._shared_cache is None:
            RecipeClient._shared_cache = self._fetch_all()
        return RecipeClient._shared_cache

    def _invalidate(self):
        RecipeClient._shared_cache = None
        RecipeClient._scaled_cache = {}

    # ── _IoProxy ─────────────────────────────────────────────────── #

    class _IoProxy:
        def __init__(self, client: "RecipeClient"):
            self._client = client

        def all(self) -> dict:
            return self._client._get_cache()

    # ── lookup helpers ────────────────────────────────────────────── #

    def _get_id_by_name(self, name: str) -> str | None:
        for rid, doc in self._get_cache().items():
            if doc.get("name") == name:
                return rid
        return None

    def _get_etag(self, recipe_id: str) -> str:
        s = get_session()
        r = s.get(f"{base_url()}/recipes/{recipe_id}")
        r.raise_for_status()
        return r.json().get("etag", "")

    # ── query API ─────────────────────────────────────────────────── #

    def get_recipe_names(self) -> list[str]:
        return [doc["name"] for doc in self._get_cache().values() if doc.get("name")]

    def get_recipes(self) -> list[tuple[str, str]]:
        """Return (name, id) tuples."""
        return [(doc["name"], rid) for rid, doc in self._get_cache().items() if doc.get("name")]

    def get_recipe_details(self, name: str) -> dict | None:
        rid = self._get_id_by_name(name)
        if rid is None:
            return None
        return self._get_cache().get(rid)

    def get_recipe_by_id(self, recipe_id: str) -> dict | None:
        return self._get_cache().get(recipe_id)

    def get_recipe_tags(self) -> list[str]:
        tags: set[str] = set()
        for doc in self._get_cache().values():
            for tag in (doc.get("tags") or []):
                tags.add(tag)
        return sorted(tags)

    def get_favourite_recipes(self) -> list[tuple[str, str]]:
        return [
            (doc["name"], rid)
            for rid, doc in self._get_cache().items()
            if doc.get("is_favourite") and doc.get("name")
        ]

    def get_scaled_ingredients(self, name: str, multiplier: int = 1) -> list[dict]:
        rid = self._get_id_by_name(name)
        if rid is None:
            return []
        key = (rid, multiplier)
        if key not in RecipeClient._scaled_cache:
            s = get_session()
            r = s.get(f"{base_url()}/recipes/{rid}/scaled", params={"multiplier": multiplier})
            r.raise_for_status()
            RecipeClient._scaled_cache[key] = r.json()
        return RecipeClient._scaled_cache[key]

    # ── mutation API ──────────────────────────────────────────────── #

    def create(
        self,
        name: str,
        servings: int,
        tags: list,
        ingredients: list,
        instructions: str,
        is_favourite: bool = False,
    ) -> bool:
        try:
            s = get_session()
            r = s.post(f"{base_url()}/recipes", json={
                "name": name,
                "servings": servings,
                "tags": tags or [],
                "ingredients": ingredients or [],
                "instructions": instructions or "",
                "is_favourite": is_favourite,
            })
            r.raise_for_status()
            self._invalidate()
            return True
        except Exception:
            return False

    def update(self, name: str, key: str, value) -> bool:
        try:
            rid = self._get_id_by_name(name)
            if rid is None:
                return False
            etag = self._get_etag(rid)
            s = get_session()
            r = s.put(
                f"{base_url()}/recipes/{rid}",
                json={key: value},
                headers={"If-Match": f'"{etag}"'},
            )
            if r.status_code == 412:
                # stale — retry once
                etag = self._get_etag(rid)
                r = s.put(
                    f"{base_url()}/recipes/{rid}",
                    json={key: value},
                    headers={"If-Match": f'"{etag}"'},
                )
            r.raise_for_status()
            self._invalidate()
            return True
        except Exception:
            return False

    def delete(self, name: str) -> bool:
        try:
            rid = self._get_id_by_name(name)
            if rid is None:
                return False
            etag = self._get_etag(rid)
            s = get_session()
            r = s.delete(
                f"{base_url()}/recipes/{rid}",
                headers={"If-Match": f'"{etag}"'},
            )
            if r.status_code == 412:
                etag = self._get_etag(rid)
                r = s.delete(
                    f"{base_url()}/recipes/{rid}",
                    headers={"If-Match": f'"{etag}"'},
                )
            r.raise_for_status()
            self._invalidate()
            return True
        except Exception:
            return False
