from __future__ import annotations

from datetime import date

from kai.core.io import IO
from kai.core import settings


class OrderHistory:
    """Tracks how many times each item has been added to the Woolworths cart.

    Stored as ``{item_name: {"count": int, "last_date": "YYYY-MM-DD"}}``.
    One order event per item per calendar day — multiple carts on the same day
    count once.
    """

    def __init__(self):
        self.io = IO(settings.data_dir() / "order_history.json")

    def record(self, item_names: list[str]) -> None:
        """Record that these items were carted today (dedup within same day)."""
        today = date.today().isoformat()
        data = self.io.all()
        changed = False
        for name in item_names:
            if not name:
                continue
            entry = data.get(name, {"count": 0, "last_date": ""})
            if entry.get("last_date") == today:
                continue  # already counted today
            entry["count"] = entry.get("count", 0) + 1
            entry["last_date"] = today
            data[name] = entry
            changed = True
        if changed:
            self.io.write(data)

    def get(self, item_name: str) -> dict:
        """Return ``{"count": int, "last_date": str}`` for one item."""
        return self.io.all().get(item_name, {"count": 0, "last_date": ""})

    def all(self) -> dict[str, dict]:
        """Return the full order history dict."""
        return self.io.all()

    def top(self, n: int = 10) -> list[tuple[str, int]]:
        """Return the top-n most ordered items as ``[(name, count)]`` sorted desc."""
        entries = [(name, d.get("count", 0)) for name, d in self.io.all().items()]
        entries.sort(key=lambda x: x[1], reverse=True)
        return entries[:n]

    def never_ordered(self, all_item_names: list[str]) -> list[str]:
        """Return item names that have never been carted."""
        history = self.io.all()
        return [n for n in all_item_names if n not in history or history[n].get("count", 0) == 0]
