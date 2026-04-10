import json
import time
from pathlib import Path
from typing import Any

# Only re-check the file's mtime over the network this often (seconds).
# Keeps SMB stat() calls to one per burst of reads instead of one per read().
_MTIME_TTL = 0.5

class IO:
    # Shared across all IO instances — keyed by resolved absolute path string
    _cache: dict[str, dict] = {}
    _cache_mtime: dict[str, float | None] = {}
    _mtime_checked_at: dict[str, float] = {}  # monotonic time of last stat()

    def __init__(self, path: str | Path):
        self.path = Path(path).resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)

        if not self.path.exists():
            self.write({})

    # ----------------- core io -----------------
    def read(self) -> dict:
        key = str(self.path)
        now = time.monotonic()

        # Skip the stat() entirely if we checked recently and have cached data.
        if key in IO._cache and (now - IO._mtime_checked_at.get(key, 0)) < _MTIME_TTL:
            return IO._cache[key]

        try:
            mtime = self.path.stat().st_mtime
        except OSError:
            mtime = None

        IO._mtime_checked_at[key] = now

        if key in IO._cache and mtime == IO._cache_mtime.get(key):
            return IO._cache[key]

        with self.path.open("r", encoding="utf-8") as f:
            IO._cache[key] = json.load(f)
        IO._cache_mtime[key] = mtime
        return IO._cache[key]

    def write(self, data: dict) -> None:
        with self.path.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
        key = str(self.path)
        IO._cache[key] = data
        try:
            mtime = self.path.stat().st_mtime
        except OSError:
            mtime = None
        IO._cache_mtime[key] = mtime
        IO._mtime_checked_at[key] = time.monotonic()

    # ----------------- CRUD -----------------
    def create(self, key: str, value: Any, overwrite: bool = False) -> None:
        data = self.read()

        if key in data and not overwrite:
            raise KeyError(f"Key already exists: {key}")

        data[key] = value
        self.write(data)

    def get(self, key: str, default: Any = None) -> Any:
        return self.read().get(key, default)

    def update(self, key: str, value: dict) -> None:
        data = self.read()

        if key not in data:
            raise KeyError(f"Key not found: {key}")

        if not isinstance(data[key], dict):
            raise TypeError(f"Data at key '{key}' is not a dict")

        data[key].update(value)
        self.write(data)


    def delete(self, key: str) -> None:
        data = self.read()

        if key not in data:
            raise KeyError(f"Key not found: {key}")

        del data[key]
        self.write(data)

    # ----------------- helpers -----------------
    def exists(self, key: str) -> bool:
        return key in self.read()

    def all(self) -> dict:
        return self.read()

    def clear(self) -> None:
        self.write({})
