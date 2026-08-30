use crate::db::settings;
use crate::error::AppError;
use crate::state::AppState;
use axum::extract::State;
use axum::routing::get;
use axum::{Json, Router};
use serde::Deserialize;

pub fn router() -> Router<AppState> {
    Router::new().route("/delivery-fee", get(get_delivery_fee).put(set_delivery_fee))
}

async fn get_delivery_fee(State(state): State<AppState>) -> Result<Json<f64>, AppError> {
    let client = state.pool.get().await?;
    Ok(Json(settings::get_delivery_fee(&client).await?))
}

#[derive(Deserialize)]
struct FeeBody {
    fee: f64,
}

async fn set_delivery_fee(
    State(state): State<AppState>,
    Json(body): Json<FeeBody>,
) -> Result<Json<f64>, AppError> {
    let client = state.pool.get().await?;
    Ok(Json(settings::set_delivery_fee(&client, body.fee).await?))
}
