from fastapi import APIRouter

from kai.objects.price_history import PriceHistory

router = APIRouter(prefix="/price-history", tags=["price-history"])


@router.get("")
def list_price_history() -> dict[str, list[dict]]:
    """Return the full price history map: {item_id: [snapshot, ...]}."""
    return PriceHistory().io.all()


@router.get("/{item_id}")
def get_price_history(item_id: str) -> list[dict]:
    """Return the price history for a single item (empty list if none)."""
    return PriceHistory().get(item_id)
