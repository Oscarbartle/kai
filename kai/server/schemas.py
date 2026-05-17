"""Pydantic schemas for the Kai API.

extra='allow' on most response models so new fields in the JSON files
don't break clients before we add them to the schema.
"""
from __future__ import annotations

from typing import Any
from pydantic import BaseModel, ConfigDict


# ── Ingredients ────────────────────────────────────────────────────── #

class Ingredient(BaseModel):
    model_config = ConfigDict(extra="allow")

    item_name: str
    amount: float = 1.0
    unit: str = "ea"
    nominal: bool = False


# ── Recipes ────────────────────────────────────────────────────────── #

class RecipeCreate(BaseModel):
    name: str
    servings: int = 1
    tags: list[str] = []
    ingredients: list[Ingredient] = []
    instructions: str = ""
    is_favourite: bool = False


class RecipeUpdate(BaseModel):
    """Partial update — all fields optional."""
    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    servings: int | None = None
    tags: list[str] | None = None
    ingredients: list[Ingredient] | None = None
    instructions: str | None = None
    is_favourite: bool | None = None


class RecipeResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    name: str
    servings: int
    tags: list[str]
    ingredients: list[Ingredient]
    instructions: str
    is_favourite: bool
    date_added: str
    etag: str


# ── Items ──────────────────────────────────────────────────────────── #

class ItemCreate(BaseModel):
    name: str
    stock_code: int
    tags: list[str] | None = None
    sold_by_weight: bool = False
    default_weight_kg: float | None = None


class ItemUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    stock_code: int | None = None
    tags: list[str] | None = None
    is_long_term: bool | None = None
    sold_by_weight: bool | None = None
    default_weight_kg: float | None = None


class ItemResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    name: str
    stock_code: int
    online_data: dict[str, Any] | None = None
    tags: list[str]
    is_long_term: bool
    sold_by_weight: bool
    default_weight_kg: float | None
    date_added: str
    date_updated: str
    etag: str


# ── Shopping lists ─────────────────────────────────────────────────── #

class RecipeEntry(BaseModel):
    recipe_name: str
    multiplier: int = 1


class ExtraItem(BaseModel):
    model_config = ConfigDict(extra="allow")

    item_name: str
    units: int = 1
    weight_kg: float | None = None


class ShoppingListGenerate(BaseModel):
    name: str = ""
    recipe_entries: list[RecipeEntry] = []
    extra_items: list[ExtraItem] = []
    exclude_long_term: bool = True
    lt_missing: list[str] = []


class ShoppingListCreate(BaseModel):
    """Create a new freeform shopping list."""
    name: str


class FreeformItemAdd(BaseModel):
    item_name: str


class FreeformRecipeAdd(BaseModel):
    recipe_id: str


class ShoppingListResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    type: str = "generated"
    name: str
    items: list[dict]
    date_generated: str
    etag: str


class ShoppingListSummary(BaseModel):
    id: str
    type: str = "generated"
    name: str
    date_generated: str
    item_count: int
