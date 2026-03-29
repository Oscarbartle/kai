import re
from difflib import SequenceMatcher

# Common quantity words/units to strip before matching
_UNITS = {
    "cup", "cups", "tablespoon", "tablespoons", "tbsp", "teaspoon",
    "teaspoons", "tsp", "oz", "ounce", "ounces", "lb", "lbs", "pound",
    "pounds", "kg", "g", "ml", "l", "litre", "litres", "liter", "liters",
    "pinch", "dash", "handful", "bunch", "sprig", "sprigs", "clove",
    "cloves", "slice", "slices", "piece", "pieces", "can", "cans",
    "tin", "tins", "packet", "package", "jar",
    "small", "medium", "large", "extra", "finely", "roughly",
    "chopped", "diced", "minced", "sliced", "grated", "crushed",
    "fresh", "dried", "ground", "whole", "halved", "quartered",
    "to", "of", "for", "and", "or", "the", "a", "an",
}

_NUM_RE = re.compile(r"^[\d\s./½¼¾⅓⅔⅛⅜⅝⅞-]+")


def _clean_ingredient(text: str) -> str:
    """Strip quantities, units, and prep words to get core ingredient name."""
    text = text.lower().strip()
    # remove parenthetical notes
    text = re.sub(r"\(.*?\)", "", text)
    # remove leading numbers / fractions
    text = _NUM_RE.sub("", text).strip()
    # remove unit words
    words = text.split()
    cleaned = [w for w in words if w.strip(",") not in _UNITS]
    return " ".join(cleaned).strip(" ,.-")


def match_ingredients(raw_ingredients: list[str], existing_items: list[str]) -> list[dict]:
    """Match raw ingredient strings to existing item names.

    Returns list of dicts: {raw_text, cleaned, best_match (str|None), confidence (float)}
    sorted by confidence descending.
    """
    existing_lower = {name.lower(): name for name in existing_items}
    results = []

    for raw in raw_ingredients:
        cleaned = _clean_ingredient(raw)
        best_match = None
        best_score = 0.0

        for lower_name, original_name in existing_lower.items():
            # try both the cleaned text and original raw text
            score = max(
                SequenceMatcher(None, cleaned, lower_name).ratio(),
                SequenceMatcher(None, raw.lower(), lower_name).ratio(),
            )
            # bonus for substring containment
            if lower_name in cleaned or cleaned in lower_name:
                score = max(score, 0.75)

            if score > best_score:
                best_score = score
                best_match = original_name

        results.append({
            "raw_text": raw,
            "cleaned": cleaned,
            "best_match": best_match if best_score >= 0.4 else None,
            "confidence": round(best_score, 3),
        })

    results.sort(key=lambda r: r["confidence"], reverse=True)
    return results
