from recipe_scrapers import scrape_html
import requests


def scrape_recipe(url: str) -> dict:
    """Fetch a recipe URL and return structured data.

    Returns dict with keys: title, servings, instructions, ingredients (list[str]).
    Raises ValueError on failure.
    """
    try:
        response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        response.raise_for_status()
    except requests.RequestException as e:
        raise ValueError(f"Failed to fetch URL: {e}") from e

    try:
        scraper = scrape_html(html=response.text, org_url=url)
    except Exception as e:
        raise ValueError(f"Could not parse recipe from this site: {e}") from e

    try:
        title = scraper.title() or ""
    except Exception:
        title = ""

    try:
        servings = scraper.yields()
        servings = int("".join(c for c in servings if c.isdigit()) or "1")
    except Exception:
        servings = 1

    try:
        instructions = scraper.instructions() or ""
    except Exception:
        instructions = ""

    try:
        ingredients = scraper.ingredients() or []
    except Exception:
        ingredients = []

    if not ingredients and not instructions:
        raise ValueError("No recipe data found at this URL")

    return {
        "title": title,
        "servings": servings,
        "instructions": instructions,
        "ingredients": ingredients,
    }
