import uuid
from datetime import datetime

from kai.core.io import IO
from kai.core import settings
from .base_model import BaseModel


class Recipe(BaseModel):
    """Recipe model: CRUD, ingredient scaling, and data migrations."""

    _migrated: set[str] = set()

    def __init__(self):
        self.io = IO(settings.data_dir() / "recipes.json")
        key = str(self.io.path)
        if key not in Recipe._migrated:
            self._migrate()
            Recipe._migrated.add(key)

    # ── migrations ─────────────────────────────────────────────────── #

    def _migrate(self):
        """Run all data migrations once per data file."""
        data = self.io.all()
        changed = False

        for recipe in data.values():
            # v1 → v2: {quantity} → {amount, unit}
            for ing in recipe.get("ingredients", []):
                if "amount" not in ing:
                    ing["amount"] = float(ing.pop("quantity", 1) or 1)
                    ing.setdefault("unit", "ea")
                    changed = True

            # v2 → v3: is_favorite → is_favourite
            if "is_favorite" in recipe:
                recipe["is_favourite"] = recipe.pop("is_favorite")
                changed = True

        if changed:
            self.io.write(data)

    # ── CRUD ─────────────────────────────────────────────────────── #

    def create(
        self,
        name: str,
        servings: int = 1,
        tags: list = None,
        ingredients: list = None,
        instructions: str = "",
        is_favourite: bool = False,
    ) -> bool:
        """Create a new recipe.  Returns False if the name already exists."""
        return self._create_record(str(uuid.uuid4()), {
            "name": name,
            "servings": servings,
            "tags": tags or [],
            "ingredients": ingredients or [],
            "instructions": instructions,
            "is_favourite": is_favourite,
            "date_added": datetime.now().isoformat(),
        })

    def update(self, name: str, key: str, value) -> bool:
        """Update a single field on an existing recipe.  Returns False on error."""
        return self._update_record(name, key, value)

    def delete(self, name: str) -> bool:
        """Delete a recipe by name.  Returns False if not found."""
        return self._delete_record(name)

    # ── queries ──────────────────────────────────────────────────── #

    def get_recipe_names(self) -> list[str]:
        return self.get_names()

    def get_recipes(self) -> list[tuple[str, str]]:
        """Return list of (recipe_name, recipe_id) tuples."""
        return self.get_all()

    def get_recipe_details(self, recipe_name: str) -> dict | None:
        return self.get_details(recipe_name)

    def get_recipe_by_id(self, recipe_id: str) -> dict | None:
        return self.io.get(recipe_id)

    def get_recipe_tags(self) -> list[str]:
        return self.get_tags()

    def get_favourite_recipes(self) -> list[tuple[str, str]]:
        return [
            (d["name"], rid)
            for rid, d in self.io.all().items()
            if d.get("is_favourite")
        ]

    # ── domain logic ───────────────────────────────────────────────── #

    def get_scaled_ingredients(self, recipe_name: str, multiplier: int) -> list[dict]:
        """Return the recipe’s ingredients with amounts multiplied by *multiplier*."""
        details = self.get_recipe_details(recipe_name)
        if not details:
            return []
        scaled = []
        for ing in details.get("ingredients", []):
            entry = dict(ing)
            entry["amount"] = (entry.get("amount") or 1) * multiplier
            scaled.append(entry)
        return scaled
