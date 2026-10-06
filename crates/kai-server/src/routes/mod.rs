mod export;
mod health;
mod ingredient_aliases;
mod items;
mod overview;
mod recipe_items;
mod recipes;
mod settings;
mod shopping_list_items;
mod shopping_lists;
mod skus;
mod tags;

use crate::auth::require_token;
use crate::state::AppState;
use axum::http::{header, HeaderValue};
use axum::middleware;
use axum::Router;
use std::path::Path;
use tower_http::services::ServeDir;
use tower_http::set_header::SetResponseHeader;

/// Everything except `/health` requires the shared token (see
/// `auth::require_token`) — a Docker healthcheck can't supply one, and
/// doesn't need to: it only proves the process and DB are up, not that
/// it's the real app talking.
pub fn build(state: AppState, shared_token: String) -> Router {
    let protected = Router::new()
        .merge(items::router())
        .merge(overview::router())
        .merge(export::router())
        .merge(ingredient_aliases::router())
        .merge(skus::router())
        .merge(tags::router())
        .merge(recipes::router())
        .merge(recipe_items::router())
        .merge(shopping_lists::router())
        .merge(shopping_list_items::router())
        .merge(settings::router())
        .merge(health::status_router())
        .layer(middleware::from_fn_with_state(shared_token, require_token));

    Router::new()
        .merge(health::health_router())
        .merge(protected)
        .with_state(state)
}

/// Serves the built mobile web app (a folder of static files) from `dir`
/// at the site root, *outside* the token check.
///
/// The files themselves hold no secrets — they're the same bundle for
/// everyone — and have to load before anyone can type a token into them.
/// Every API route is still behind `require_token` exactly as before; this
/// only ever answers for paths the API doesn't own, so it can't shadow one.
///
/// Because the app and the API come from the same address, the browser
/// treats calls between them as same-origin: no CORS configuration needed.
///
/// No SPA catch-all on purpose: an unknown path should 404, not quietly
/// return `index.html` with a 200 — that would turn a mistyped API route
/// into an HTML page a JSON client chokes on with a confusing parse error.
///
/// `Cache-Control: no-cache` means "revalidate every time", which is cheap
/// (a 304 when nothing changed) and means a redeploy reaches phones on
/// their next open instead of whenever a heuristic cache happens to expire.
pub fn with_static_files(router: Router, dir: impl AsRef<Path>) -> Router {
    let files = SetResponseHeader::overriding(
        ServeDir::new(dir),
        header::CACHE_CONTROL,
        HeaderValue::from_static("no-cache"),
    );
    router.fallback_service(files)
}
