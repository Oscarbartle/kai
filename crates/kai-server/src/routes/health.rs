//! `/health` (unauthenticated — the Docker healthcheck can't supply a
//! token, and it only needs to know the process + DB are alive) and
//! `/status` (authenticated — what the app's "Test connection" button
//! hits, so a successful call proves both reachability *and* the token
//! at once).

use crate::error::AppError;
use crate::state::AppState;
use axum::extract::State;
use axum::routing::get;
use axum::{Json, Router};
use serde_json::{json, Value};

pub fn health_router() -> Router<AppState> {
    Router::new().route("/health", get(health))
}

pub fn status_router() -> Router<AppState> {
    Router::new().route("/status", get(status))
}

async fn health(State(state): State<AppState>) -> Result<Json<Value>, AppError> {
    let client = state.pool.get().await?;
    client
        .query_one("SELECT 1", &[])
        .await
        .map_err(|e| AppError::internal(format!("Database unreachable: {e}")))?;
    Ok(Json(json!({ "ok": true })))
}

async fn status() -> Json<Value> {
    Json(json!({ "ok": true }))
}
