import uuid
from datetime import datetime

from kai.core.io import IO
from kai.core import settings

class Recipe:
    def __init__(self):
        self.io = IO(settings.data_dir() / "recipes.json")
        self._migrate()

    def _migrate(self):
        """Migrate old {item_name, quantity} ingredients to {item_name, amount, unit}"""
        data = self.io.all()
        changed = False
        for recipe_id, recipe in data.items():
            for ing in recipe.get("ingredients", []):
                if "amount" not in ing:
                    ing["amount"] = float(ing.pop("quantity", 1) or 1)
                    ing.setdefault("unit", "ea")
                    changed = True
        if changed:
            self.io.write(data)
        self._migrate_favourite()

    def _migrate_favourite(self):
        """Rename is_favorite to is_favourite in existing data."""
        data = self.io.all()
        changed = False
        for recipe_id, recipe in data.items():
            if "is_favorite" in recipe:
                recipe["is_favourite"] = recipe.pop("is_favorite")
                changed = True
        if changed:
            self.io.write(data)

    def _name_exists(self, name: str):
        """Check if a recipe with this name already exists"""
        all_recipes = self.io.all()
        return any(data.get("name") == name for data in all_recipes.values())

    def _get_id_by_name(self, name: str):
        """Get recipe ID by name"""
        all_recipes = self.io.all()
        for recipe_id, data in all_recipes.items():
            if data.get("name") == name:
                return recipe_id
        return None

    def create(self, name: str, servings: int = 1, tags: list = None,
               ingredients: list = None, instructions: str = "", is_favourite: bool = False):
        recipe_id = str(uuid.uuid4())

        if not self._name_exists(name):
            self.io.create(recipe_id, {}, overwrite=True)
            self.io.update(recipe_id, {
                "name": name,
                "servings": servings,
                "tags": tags or [],
                "ingredients": ingredients or [],
                "instructions": instructions,
                "is_favourite": is_favourite,
                "date_added": datetime.now().isoformat()
            })
            print(f"Recipe '{name}' has been added")
        else:
            print("Recipe already exists")

    def update(self, name: str, key: str, value):
        if key == "id":
            return print("You cannot edit the id")

        recipe_id = self._get_id_by_name(name)
        if recipe_id:
            self.io.update(recipe_id, {key: value})
        else:
            return print("Recipe does not exist please create it")

    def delete(self, name: str):
        recipe_id = self._get_id_by_name(name)
        if recipe_id:
            self.io.delete(recipe_id)
        else:
            print("Recipe does not exist")

    # ----- Queries ----- #

    def get_recipe_names(self):
        all_recipes = self.io.all()
        return [data["name"] for data in all_recipes.values()]

    def get_recipes(self):
        """Returns list of tuples: (recipe_name, recipe_id)"""
        all_recipes = self.io.all()
        return [(data["name"], recipe_id) for recipe_id, data in all_recipes.items()]

    def get_recipe_details(self, recipe_name: str):
        recipe_id = self._get_id_by_name(recipe_name)
        if recipe_id:
            return self.io.all()[recipe_id]
        return None

    def get_recipe_by_id(self, recipe_id: str):
        return self.io.get(recipe_id)

    def get_recipe_tags(self):
        tags = []
        all_recipes = self.io.all()
        for data in all_recipes.values():
            doc_tags = data.get("tags")
            if doc_tags:
                tags.extend(doc_tags)
        return list(set(tags))

    def get_favourite_recipes(self):
        all_recipes = self.io.all()
        return [(data["name"], rid) for rid, data in all_recipes.items() if data.get("is_favourite")]

    def get_scaled_ingredients(self, recipe_name: str, multiplier: int):
        """Return ingredients with quantities multiplied"""
        details = self.get_recipe_details(recipe_name)
        if not details:
            return []

        scaled = []
        for ing in details.get("ingredients", []):
            entry = dict(ing)
            amount = entry.get("amount", 1) or 1
            entry["amount"] = amount * multiplier
            scaled.append(entry)

        return scaled
