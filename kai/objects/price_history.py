from __future__ import annotations

from datetime import datetime, timedelta

from kai.core.io import IO
from kai.core import settings


class PriceHistory:
    """Stores per-item price snapshots keyed by item UUID."""

    def __init__(self):
        self.io = IO(settings.data_dir() / "price_history.json")

    def record(self, item_id: str, snapshot: dict) -> None:
        """Append a snapshot unless the last one is identical (dedup)."""
        data = self.io.all()
        history = data.get(item_id, [])

        if history:
            last = history[-1]
            if (
                last.get("current_price") == snapshot.get("current_price")
                and last.get("original_price") == snapshot.get("original_price")
                and last.get("on_special") == snapshot.get("on_special")
            ):
                return

        history.append({
            "date": snapshot.get("date") or datetime.now().isoformat(),
            "current_price": snapshot.get("current_price"),
            "original_price": snapshot.get("original_price"),
            "on_special": snapshot.get("on_special", False),
            "discount_pct": snapshot.get("discount_pct", ""),
        })
        data[item_id] = history
        self.io.write(data)

    def get(self, item_id: str) -> list[dict]:
        return self.io.all().get(item_id, [])

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
        """Return the last *limit* snapshots that were on special."""
        specials = [s for s in self.get(item_id) if s.get("on_special")]
        return specials[-limit:]
