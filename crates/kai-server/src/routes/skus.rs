use crate::db::skus;
use crate::error::AppError;
use crate::state::AppState;
use axum::extract::{Path, State};
use axum::routing::{get, patch};
use axum::{Json, Router};
use kai_shared::skus::{Sku, StoredSku};
use serde::Deserialize;

pub fn router() -> Router<AppState> {
    Router::new()
        .route("/items/{item_id}/skus", get(list_skus_for_item).post(save_sku_to_item))
        .route("/skus/{id}", get(get_sku).delete(delete_sku))
        .route("/skus/{id}/preferred", patch(set_sku_preferred))
}

async fn list_skus_for_item(
    State(state): State<AppState>,
    Path(item_id): Path<i64>,
) -> Result<Json<Vec<StoredSku>>, AppError> {
    let client = state.pool.get().await?;
    Ok(Json(skus::list_for_item(&client, item_id).await?))
}

async fn save_sku_to_item(
    State(state): State<AppState>,
    Path(item_id): Path<i64>,
    Json(sku): Json<Sku>,
) -> Result<Json<StoredSku>, AppError> {
    let client = state.pool.get().await?;
    Ok(Json(skus::save(&client, item_id, &sku).await?))
}

async fn get_sku(State(state): State<AppState>, Path(id): Path<i64>) -> Result<Json<StoredSku>, AppError> {
    let client = state.pool.get().await?;
    Ok(Json(skus::get(&client, id).await?))
}

async fn delete_sku(State(state): State<AppState>, Path(id): Path<i64>) -> Result<(), AppError> {
    let client = state.pool.get().await?;
    skus::delete(&client, id).await?;
    Ok(())
}

#[derive(Deserialize)]
struct PreferredBody {
    is_preferred: bool,
}

async fn set_sku_preferred(
    State(state): State<AppState>,
    Path(id): Path<i64>,
    Json(body): Json<PreferredBody>,
) -> Result<Json<StoredSku>, AppError> {
    let client = state.pool.get().await?;
    Ok(Json(skus::set_preferred(&client, id, body.is_preferred).await?))
}
