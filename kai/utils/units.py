"""Unit conversion utilities used across Item, ShoppingList, and display helpers.

All public functions are pure — no IO, no state.
"""
from __future__ import annotations

# ── constants ─────────────────────────────────────────────────────── #

# Maps lowercase unit alias → (canonical_base_unit, multiplier_to_base)
_TO_BASE: dict[str, tuple[str, float]] = {
    "g":    ("g",  1.0),
    "kg":   ("g",  1000.0),
    "ml":   ("mL", 1.0),
    "mL":   ("mL", 1.0),
    "l":    ("mL", 1000.0),
    "L":    ("mL", 1000.0),
    "ea":   ("ea", 1.0),
}

# Pairs of base units that are mutually convertible
_COMPATIBLE: set[frozenset[str]] = {
    frozenset({"g"}),
    frozenset({"mL"}),
    frozenset({"ea"}),
}


# ── public API ────────────────────────────────────────────────────── #

def to_base(amount: float, unit: str) -> tuple[float, str]:
    """Convert *amount* in *unit* to its canonical base unit.

    Returns ``(converted_amount, base_unit)`` where base_unit is one of
    ``"g"``, ``"mL"``, or ``"ea"``.

    Unknown units are treated as ``"ea"`` with a 1:1 ratio.

    >>> to_base(1.5, "kg")
    (1500.0, 'g')
    >>> to_base(500, "mL")
    (500.0, 'mL')
    >>> to_base(3, "ea")
    (3.0, 'ea')
    """
    base_unit, factor = _TO_BASE.get(unit, _TO_BASE.get(unit.lower(), ("ea", 1.0)))
    return amount * factor, base_unit


def units_compatible(unit_a: str, unit_b: str) -> bool:
    """Return True if two units can be meaningfully summed (same base family).

    >>> units_compatible("g", "kg")
    True
    >>> units_compatible("g", "mL")
    False
    """
    _, base_a = _TO_BASE.get(unit_a, _TO_BASE.get(unit_a.lower(), ("ea", 1.0)))
    _, base_b = _TO_BASE.get(unit_b, _TO_BASE.get(unit_b.lower(), ("ea", 1.0)))
    return base_a == base_b


def format_amount(amount: float, base_unit: str) -> tuple[float, str]:
    """Convert a base-unit amount to a human-readable (amount, display_unit) pair.

    Large gram amounts are converted to kg; large mL amounts to L.

    >>> format_amount(1500, "g")
    (1.5, 'kg')
    >>> format_amount(250, "mL")
    (250.0, 'mL')
    """
    if base_unit == "g" and amount >= 1000:
        return round(amount / 1000, 2), "kg"
    if base_unit == "mL" and amount >= 1000:
        return round(amount / 1000, 2), "L"
    return round(amount, 1), base_unit


def parse_woolworths_measure(cup_price: float, measure: str) -> float | None:
    """Convert a Woolworths ``Price per Kg/Unit`` value to a price per 100 g/mL.

    Returns None if the measure string cannot be interpreted.
    """
    m = measure.lower().strip()
    if not m or cup_price is None:
        return None
    if "kg" in m:
        return round(cup_price / 10, 2)
    if "100g" in m or "100ml" in m:
        return round(cup_price, 2)
    if "l" in m:
        return round(cup_price / 10, 2)
    return round(cup_price, 2)


def derive_package_size(
    price: float,
    cup_price: float,
    measure: str,
    avg_weight: float | None,
) -> tuple[int | None, str | None]:
    """Derive package size (amount, unit) from Woolworths pricing metadata.

    Returns ``(size_in_base_units, base_unit)`` such as ``(400, "g")``,
    ``(1000, "mL")``, or ``(1, "ea")``.
    Returns ``(None, None)`` if there is not enough information.
    """
    if not price or not cup_price or cup_price == 0:
        if avg_weight and avg_weight > 0:
            return round(avg_weight * 1000), "g"
        return None, None

    ratio = price / cup_price
    m = (measure or "").lower().strip()

    if "kg" in m:
        return round(ratio * 1000), "g"
    if "100g" in m:
        return round(ratio * 100), "g"
    if "100ml" in m:
        return round(ratio * 100), "mL"
    if "l" in m:
        return round(ratio * 1000), "mL"
    if avg_weight and avg_weight > 0:
        return round(avg_weight * 1000), "g"
    return 1, "ea"
