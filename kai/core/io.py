import json
from pathlib import Path
from typing import Any

class IO:

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

        if not self.path.exists():
            self.write({})

    # ----------------- core io -----------------
    def read(self) -> dict:
        with self.path.open("r", encoding="utf-8") as f:
            return json.load(f)

    def write(self, data: dict) -> None:
        with self.path.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)

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
