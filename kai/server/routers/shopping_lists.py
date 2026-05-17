from fastapi import APIRouter, HTTPException, Header, Response
from typing import Annotated

from kai.objects.shopping_list import ShoppingList
from kai.server.schemas import (
    ShoppingListGenerate,
    ShoppingListResponse,
    ShoppingListSummary,
)
from kai.server.etag import record_etag, check_etag

router = APIRouter(prefix="/shopping-lists", tags=["shopping-lists"])


def _list_response(list_id: str, data: dict) -> ShoppingListResponse:
    return ShoppingListResponse(id=list_id, etag=record_etag(data), **data)


@router.get("", response_model=list[ShoppingListSummary])
def list_shopping_lists():
    obj = ShoppingList()
    return [
        ShoppingListSummary(
            id=lid,
            name=name,
            date_generated=date,
            item_count=len(obj.io.get(lid).get("items", [])),
        )
        for name, lid, date in obj.get_all_lists()
    ]


@router.post("/generate", response_model=ShoppingListResponse, status_code=201)
def generate_shopping_list(body: ShoppingListGenerate, response: Response):
    """Generate a new shopping list from recipes and optional extra items."""
    obj = ShoppingList()
    list_id = obj.generate(
        recipe_entries=[e.model_dump() for e in body.recipe_entries],
        exclude_long_term=body.exclude_long_term,
        name=body.name,
        extra_items=[e.model_dump() for e in body.extra_items],
        lt_missing=body.lt_missing,
    )
    data = obj.io.get(list_id)
    response.headers["ETag"] = f'"{record_etag(data)}"'
    return _list_response(list_id, data)


@router.get("/{list_id}", response_model=ShoppingListResponse)
def get_shopping_list(list_id: str, response: Response):
    obj = ShoppingList()
    data = obj.get_list(list_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Shopping list not found.")
    response.headers["ETag"] = f'"{record_etag(data)}"'
    return _list_response(list_id, data)


@router.delete("/{list_id}", status_code=204)
def delete_shopping_list(
    list_id: str,
    if_match: Annotated[str | None, Header()] = None,
):
    obj = ShoppingList()
    data = obj.get_list(list_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Shopping list not found.")
    check_etag(data, if_match)
    obj.delete_list(list_id)


@router.patch("/{list_id}/items/{item_name}/purchased", response_model=ShoppingListResponse)
def toggle_purchased(
    list_id: str,
    item_name: str,
    purchased: bool,
    response: Response,
    if_match: Annotated[str | None, Header()] = None,
):
    """Mark an item as purchased or not purchased."""
    obj = ShoppingList()
    data = obj.get_list(list_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Shopping list not found.")
    check_etag(data, if_match)
    obj.mark_purchased(list_id, item_name, purchased)
    updated = obj.get_list(list_id)
    response.headers["ETag"] = f'"{record_etag(updated)}"'
    return _list_response(list_id, updated)
