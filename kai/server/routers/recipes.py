from fastapi import APIRouter, HTTPException, Header, Response
from typing import Annotated

from kai.objects.recipe import Recipe
from kai.server.schemas import RecipeCreate, RecipeUpdate, RecipeResponse
from kai.server.etag import record_etag, check_etag

router = APIRouter(prefix="/recipes", tags=["recipes"])


def _recipe_response(recipe_id: str, data: dict) -> RecipeResponse:
    etag = record_etag(data)
    return RecipeResponse(id=recipe_id, etag=etag, **data)


@router.get("", response_model=list[RecipeResponse])
def list_recipes():
    obj = Recipe()
    all_data = obj.io.all()
    return [_recipe_response(rid, d) for rid, d in all_data.items()]


@router.post("", response_model=RecipeResponse, status_code=201)
def create_recipe(body: RecipeCreate, response: Response):
    obj = Recipe()
    ok = obj.create(
        name=body.name,
        servings=body.servings,
        tags=body.tags,
        ingredients=[i.model_dump() for i in body.ingredients],
        instructions=body.instructions,
        is_favourite=body.is_favourite,
    )
    if not ok:
        raise HTTPException(status_code=409, detail=f"Recipe '{body.name}' already exists.")
    recipe_id = obj._get_id_by_name(body.name)
    data = obj.io.get(recipe_id)
    response.headers["ETag"] = f'"{record_etag(data)}"'
    return _recipe_response(recipe_id, data)


@router.get("/{recipe_id}", response_model=RecipeResponse)
def get_recipe(recipe_id: str, response: Response):
    obj = Recipe()
    data = obj.io.get(recipe_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Recipe not found.")
    response.headers["ETag"] = f'"{record_etag(data)}"'
    return _recipe_response(recipe_id, data)


@router.put("/{recipe_id}", response_model=RecipeResponse)
def update_recipe(
    recipe_id: str,
    body: RecipeUpdate,
    response: Response,
    if_match: Annotated[str | None, Header()] = None,
):
    obj = Recipe()
    data = obj.io.get(recipe_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Recipe not found.")
    check_etag(data, if_match)

    updates = body.model_dump(exclude_none=True)
    if "ingredients" in updates:
        updates["ingredients"] = [
            i.model_dump() if hasattr(i, "model_dump") else i
            for i in updates["ingredients"]
        ]
    obj.io.update(recipe_id, updates)
    updated = obj.io.get(recipe_id)
    response.headers["ETag"] = f'"{record_etag(updated)}"'
    return _recipe_response(recipe_id, updated)


@router.delete("/{recipe_id}", status_code=204)
def delete_recipe(
    recipe_id: str,
    if_match: Annotated[str | None, Header()] = None,
):
    obj = Recipe()
    data = obj.io.get(recipe_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Recipe not found.")
    check_etag(data, if_match)
    obj.io.delete(recipe_id)


@router.get("/{recipe_id}/scaled", response_model=list[dict])
def get_scaled_recipe(recipe_id: str, multiplier: int = 1):
    obj = Recipe()
    data = obj.io.get(recipe_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Recipe not found.")
    return obj.get_scaled_ingredients(data["name"], multiplier)
