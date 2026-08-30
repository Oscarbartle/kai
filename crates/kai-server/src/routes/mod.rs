mod health;
mod items;
mod recipe_items;
mod recipes;
mod settings;
mod shopping_list_items;
mod shopping_lists;
mod skus;
mod tags;

use crate::auth::require_token;
use crate::state::AppState;
use axum::middleware;
use axum::Router;

/// Everything except `/health` requires the shared token (see
/// `auth::require_token`) — a Docker healthcheck can't supply one, and
/// doesn't need to: it only proves the process and DB are up, not that
/// it's the real app talking.
pub fn build(state: AppState, shared_token: String) -> Router {
    let protected = Router::new()
        .merge(items::router())
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
