//! Shared-token auth — a single `KAI_SHARED_TOKEN` env var, checked
//! against every request's `Authorization: Bearer <token>` header. Not
//! per-user login: this is a household-shared server (see CLAUDE.md's
//! Phase B notes — Oscar + partner, not a multi-tenant service), so one
//! secret both devices know is proportionate. Applied to every route
//! except `/health` (the Docker healthcheck, which can't supply a token).

use axum::extract::State;
use axum::http::{Request, StatusCode};
use axum::middleware::Next;
use axum::response::Response;

pub async fn require_token(
    State(expected_token): State<String>,
    request: Request<axum::body::Body>,
    next: Next,
) -> Result<Response, StatusCode> {
    let header = request
        .headers()
        .get(axum::http::header::AUTHORIZATION)
        .and_then(|v| v.to_str().ok());

    match header.and_then(|h| h.strip_prefix("Bearer ")) {
        Some(token) if token == expected_token => Ok(next.run(request).await),
        _ => Err(StatusCode::UNAUTHORIZED),
    }
}
