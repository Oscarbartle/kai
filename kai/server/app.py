"""FastAPI application factory for the Kai server."""
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from kai.server import config
from kai.server.routers import items, price_history, recipes, shopping_lists


@asynccontextmanager
async def _lifespan(app: FastAPI):
    # Point all model classes at the configured data directory before any
    # request handler instantiates them.  We monkey-patch settings.data_dir
    # so Recipe/Item/ShoppingList constructors pick it up without modification.
    from kai.core import settings as _settings
    _settings.data_dir = lambda: config.DATA_DIR  # type: ignore[method-assign]

    # Run migrations once at startup (Recipe._migrate runs on first instantiation
    # when _migrated set is empty; this just warms the cache early).
    from kai.objects.recipe import Recipe
    from kai.objects.item import Item
    Recipe()
    Item()

    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="Kai API",
        description="Backend for the Kai meal prep system.",
        version="1.0.0",
        lifespan=_lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["ETag"],
    )

    app.include_router(recipes.router)
    app.include_router(items.router)
    app.include_router(price_history.router)
    app.include_router(shopping_lists.router)

    @app.get("/health")
    def health():
        return {"status": "ok", "data_dir": str(config.DATA_DIR)}

    return app


app = create_app()
