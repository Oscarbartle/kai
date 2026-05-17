from fastapi import APIRouter, HTTPException, Header, Response
from typing import Annotated

from kai.objects.item import Item
from kai.server.schemas import ItemCreate, ItemUpdate, ItemResponse
from kai.server.etag import record_etag, check_etag

router = APIRouter(prefix="/items", tags=["items"])


def _item_response(item_id: str, data: dict) -> ItemResponse:
    etag = record_etag(data)
    return ItemResponse(id=item_id, etag=etag, **data)


@router.get("", response_model=list[ItemResponse])
def list_items():
    obj = Item()
    return [_item_response(iid, d) for iid, d in obj.io.all().items()]


@router.post("", response_model=ItemResponse, status_code=201)
def create_item(body: ItemCreate, response: Response):
    obj = Item()
    ok = obj.create(
        name=body.name,
        stock_code=body.stock_code,
        tags=body.tags,
        sold_by_weight=body.sold_by_weight,
        default_weight_kg=body.default_weight_kg,
    )
    if not ok:
        raise HTTPException(status_code=409, detail=f"Item '{body.name}' already exists.")
    item_id = obj._get_id_by_name(body.name)
    data = obj.io.get(item_id)
    response.headers["ETag"] = f'"{record_etag(data)}"'
    return _item_response(item_id, data)


@router.get("/{item_id}", response_model=ItemResponse)
def get_item(item_id: str, response: Response):
    obj = Item()
    data = obj.io.get(item_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Item not found.")
    response.headers["ETag"] = f'"{record_etag(data)}"'
    return _item_response(item_id, data)


@router.put("/{item_id}", response_model=ItemResponse)
def update_item(
    item_id: str,
    body: ItemUpdate,
    response: Response,
    if_match: Annotated[str | None, Header()] = None,
):
    obj = Item()
    data = obj.io.get(item_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Item not found.")
    check_etag(data, if_match)

    obj.io.update(item_id, body.model_dump(exclude_none=True))
    updated = obj.io.get(item_id)
    response.headers["ETag"] = f'"{record_etag(updated)}"'
    return _item_response(item_id, updated)


@router.delete("/{item_id}", status_code=204)
def delete_item(
    item_id: str,
    if_match: Annotated[str | None, Header()] = None,
):
    obj = Item()
    data = obj.io.get(item_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Item not found.")
    check_etag(data, if_match)
    obj.io.delete(item_id)


@router.post("/{item_id}/refresh", response_model=ItemResponse)
def refresh_item_price(item_id: str, response: Response):
    """Re-fetch Woolworths pricing data for this item."""
    obj = Item()
    data = obj.io.get(item_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Item not found.")
    obj.refresh_online_data(data["name"])
    updated = obj.io.get(item_id)
    response.headers["ETag"] = f'"{record_etag(updated)}"'
    return _item_response(item_id, updated)
