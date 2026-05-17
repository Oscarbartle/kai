from fastapi import APIRouter, HTTPException, Header, Response
from typing import Annotated

from kai.objects.shopping_list import ShoppingList
from kai.server.schemas import (
    ShoppingListGenerate,
    ShoppingListCreate,
    FreeformItemAdd,
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


@router.post("", response_model=ShoppingListResponse, status_code=201)
def create_freeform_list(body: ShoppingListCreate, response: Response):
    """Create a new named freeform shopping list."""
    obj = ShoppingList()
    list_id = obj.create_freeform(body.name)
    data = obj.get_list(list_id)
    response.headers["ETag"] = f'"{record_etag(data)}"'
    return _list_response(list_id, data)


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


@router.patch("/{list_id}/rename", response_model=ShoppingListResponse)
def rename_list(
    list_id: str,
    body: ShoppingListCreate,
    response: Response,
    if_match: Annotated[str | None, Header()] = None,
):
    """Rename a shopping list."""
    obj = ShoppingList()
    data = obj.get_list(list_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Shopping list not found.")
    check_etag(data, if_match)
    obj.io.update(list_id, {"name": body.name})
    updated = obj.get_list(list_id)
    response.headers["ETag"] = f'"{record_etag(updated)}"'
    return _list_response(list_id, updated)


@router.post("/{list_id}/items", response_model=ShoppingListResponse, status_code=201)
def add_item_to_freeform(
    list_id: str,
    body: FreeformItemAdd,
    response: Response,
    if_match: Annotated[str | None, Header()] = None,
):
    """Add an item to a freeform list. Unrecognised items are flagged with recognised=False."""
    obj = ShoppingList()
    data = obj.get_list(list_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Shopping list not found.")
    if data.get("type") != "freeform":
        raise HTTPException(status_code=400, detail="Items can only be added to freeform lists.")
    check_etag(data, if_match)
    obj.freeform_add_item(list_id, body.item_name)
    updated = obj.get_list(list_id)
    response.headers["ETag"] = f'"{record_etag(updated)}"'
    return _list_response(list_id, updated)


@router.delete("/{list_id}/items/{item_name}", response_model=ShoppingListResponse)
def remove_item_from_freeform(
    list_id: str,
    item_name: str,
    response: Response,
    if_match: Annotated[str | None, Header()] = None,
):
    """Remove an item from a freeform list."""
    obj = ShoppingList()
    data = obj.get_list(list_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Shopping list not found.")
    if data.get("type") != "freeform":
        raise HTTPException(status_code=400, detail="Items can only be removed from freeform lists.")
    check_etag(data, if_match)
    ok = obj.freeform_remove_item(list_id, item_name)
    if not ok:
        raise HTTPException(status_code=404, detail=f"Item '{item_name}' not found in list.")
    updated = obj.get_list(list_id)
    response.headers["ETag"] = f'"{record_etag(updated)}"'
    return _list_response(list_id, updated)


@router.post("/{list_id}/items/{item_name}/link", response_model=ShoppingListResponse)
def link_item(
    list_id: str,
    item_name: str,
    response: Response,
    if_match: Annotated[str | None, Header()] = None,
):
    """Re-resolve an unrecognised item against the pantry (call after adding it to items)."""
    obj = ShoppingList()
    data = obj.get_list(list_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Shopping list not found.")
    check_etag(data, if_match)
    ok = obj.freeform_link_item(list_id, item_name)
    if not ok:
        raise HTTPException(status_code=404, detail=f"Item '{item_name}' not found in pantry.")
    updated = obj.get_list(list_id)
    response.headers["ETag"] = f'"{record_etag(updated)}"'
    return _list_response(list_id, updated)
