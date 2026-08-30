//! HTTP-facing error wrapper. `db::*` functions here return plain
//! `Result<T, String>` — the exact same convention `src-tauri/src/db/*.rs`
//! uses — so the *message* a client sees is identical regardless of which
//! backend answered it. This type only adds the HTTP status code at the
//! route-handler boundary; the message itself is untouched.

use axum::http::StatusCode;
use axum::response::{IntoResponse, Response};
use axum::Json;
use serde_json::json;

pub struct AppError {
    pub status: StatusCode,
    pub message: String,
}

impl AppError {
    pub fn bad_request(message: impl Into<String>) -> Self {
        Self { status: StatusCode::BAD_REQUEST, message: message.into() }
    }

    pub fn internal(message: impl Into<String>) -> Self {
        Self { status: StatusCode::INTERNAL_SERVER_ERROR, message: message.into() }
    }
}

/// `db::*` functions' own errors (a plain `String`, same as the SQLite
/// side) become a 400 — the request was understood but the operation
/// itself failed for an application reason ("No item with id 4", "Can't
/// delete — used in: ..."). Only pool/connection failures (see below) are
/// 500s — those are genuinely this server's own problem, not the caller's.
impl From<String> for AppError {
    fn from(message: String) -> Self {
        AppError::bad_request(message)
    }
}

impl From<deadpool_postgres::PoolError> for AppError {
    fn from(e: deadpool_postgres::PoolError) -> Self {
        AppError::internal(format!("Couldn't get a database connection: {e}"))
    }
}

impl IntoResponse for AppError {
    fn into_response(self) -> Response {
        (self.status, Json(json!({ "error": self.message }))).into_response()
    }
}
