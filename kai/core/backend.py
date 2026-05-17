import os


def _is_remote() -> bool:
    return os.environ.get("KAI_BACKEND", "local").lower() == "remote"


def get_recipe():
    if _is_remote():
        from kai.clients.recipe_client import RecipeClient
        return RecipeClient()
    from kai.objects.recipe import Recipe
    return Recipe()


def get_item():
    if _is_remote():
        from kai.clients.item_client import ItemClient
        return ItemClient()
    from kai.objects.item import Item
    return Item()


def get_shopping_list():
    if _is_remote():
        from kai.clients.shopping_list_client import ShoppingListClient
        return ShoppingListClient()
    from kai.objects.shopping_list import ShoppingList
    return ShoppingList()
