"""HTTP client for the /price-history API endpoints.

Mirrors the surface of kai.objects.price_history.PriceHistory so call sites
can swap between them via kai.core.backend.get_price_history().
"""
from __future__ import annotations

from datetime import datetime, timedelta

from kai.clients.http import get_session, base_url


class PriceHistoryClient:
    _shared_cache: dict | None = None  # {item_id: [snapshot, ...]}

    # ── cache ─────────────────────────────────────────────────────── #

    def _fetch_all(self) -> dict:
        s = get_session()
        r = s.get(f"{base_url()}/price-history")
        r.raise_for_status()
        return r.json()

    def _get_cache(self) -> dict:
        if PriceHistoryClient._shared_cache is None:
            try:
                PriceHistoryClient._shared_cache = self._fetch_all()
            except Exception:
                return {}
        return PriceHistoryClient._shared_cache

    @classmethod
    def invalidate(cls) -> None:
        cls._shared_cache = None

    # ── read API (mirrors PriceHistory) ───────────────────────────── #

    def get(self, item_id: str) -> list[dict]:
        return self._get_cache().get(item_id, [])

    def min_in_window(self, item_id: str, days: int) -> float | None:
        cutoff = datetime.now() - timedelta(days=days)
        prices = []
        for snap in self.get(item_id):
            try:
                if datetime.fromisoformat(snap["date"]) >= cutoff:
                    p = snap.get("current_price")
                    if p is not None:
                        prices.append(float(p))
            except (ValueError, TypeError):
                continue
        return min(prices) if prices else None

    def all_time_min(self, item_id: str) -> float | None:
        prices = [
            float(s["current_price"])
            for s in self.get(item_id)
            if s.get("current_price") is not None
        ]
        return min(prices) if prices else None

    def all_time_max(self, item_id: str) -> float | None:
        prices = [
            float(s["current_price"])
            for s in self.get(item_id)
            if s.get("current_price") is not None
        ]
        return max(prices) if prices else None

    def avg_in_window(self, item_id: str, days: int) -> float | None:
        cutoff = datetime.now() - timedelta(days=days)
        prices = []
        for snap in self.get(item_id):
            try:
                if datetime.fromisoformat(snap["date"]) >= cutoff:
                    p = snap.get("current_price")
                    if p is not None:
                        prices.append(float(p))
            except (ValueError, TypeError):
                continue
        return round(sum(prices) / len(prices), 2) if prices else None

    def recent_specials(self, item_id: str, limit: int = 5) -> list[dict]:
        specials = [s for s in self.get(item_id) if s.get("on_special")]
        return specials[-limit:]
