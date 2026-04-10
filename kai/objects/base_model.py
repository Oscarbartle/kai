"""Shared CRUD base class for Item and Recipe.

Subclasses supply ``_io`` (an IO instance) and call ``super().__init__()``
after setting it.  Domain-specific logic (pricing, scaling, migrations)
lives in the subclass.
"""
from __future__ import annotations


class BaseModel:
    """Common name-keyed CRUD operations backed by an IO instance."""

    # Subclass must set self.io before calling super().__init__()

    # ── lookups ──────────────────────────────────────────────────── #

    def _name_exists(self, name: str) -> bool:
        """Return True if a record with this name already exists."""
        return any(d.get("name") == name for d in self.io.all().values())

    def _get_id_by_name(self, name: str) -> str | None:
        """Return the UUID key for the record with the given name, or None."""
        for record_id, data in self.io.all().items():
            if data.get("name") == name:
                return record_id
        return None

    # ── write ────────────────────────────────────────────────────── #

    def _create_record(self, record_id: str, fields: dict) -> bool:
        """Persist a new record.  Returns False if the name already exists."""
        if self._name_exists(fields.get("name", "")):
            return False
        self.io.create(record_id, {}, overwrite=True)
        self.io.update(record_id, fields)
        return True

    def _update_record(self, name: str, key: str, value) -> bool:
        """Update a single field on an existing record.  Returns False on error."""
        if key == "id":
            return False
        record_id = self._get_id_by_name(name)
        if not record_id:
            return False
        self.io.update(record_id, {key: value})
        return True

    def _delete_record(self, name: str) -> bool:
        """Delete a record by name.  Returns False if not found."""
        record_id = self._get_id_by_name(name)
        if not record_id:
            return False
        self.io.delete(record_id)
        return True

    # ── read ─────────────────────────────────────────────────────── #

    def get_names(self) -> list[str]:
        """Return all record names."""
        return [d["name"] for d in self.io.all().values()]

    def get_all(self) -> list[tuple[str, str]]:
        """Return list of (name, record_id) tuples."""
        return [(d["name"], rid) for rid, d in self.io.all().items()]

    def get_details(self, name: str) -> dict | None:
        """Return the full record dict for the given name, or None."""
        record_id = self._get_id_by_name(name)
        if record_id:
            return self.io.all()[record_id]
        return None

    def get_tags(self) -> list[str]:
        """Return deduplicated list of all tags across all records."""
        tags: list[str] = []
        for data in self.io.all().values():
            doc_tags = data.get("tags")
            if doc_tags:
                tags.extend(doc_tags)
        return list(set(tags))
