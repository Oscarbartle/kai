use crate::db::shopping_lists;
use crate::error::AppError;
use crate::state::AppState;
use axum::extract::{Path, State};
use axum::routing::{get, patch};
use axum::{Json, Router};
use kai_shared::shopping_lists::ShoppingList;
use serde::Deserialize;

pub fn router() -> Router<AppState> {
    Router::new()
        .route("/shopping-lists", get(list_shopping_lists).post(create_shopping_list))
        .route("/shopping-lists/{id}", axum::routing::delete(delete_shopping_list))
        .route("/shopping-lists/{id}/name", patch(update_shopping_list_name))
}

async fn list_shopping_lists(State(state): State<AppState>) -> Result<Json<Vec<ShoppingList>>, AppError> {
    let client = state.pool.get().await?;
    Ok(Json(shopping_lists::list(&client).await?))
}

#[derive(Deserialize)]
struct NameBody {
    name: String,
}

async fn create_shopping_list(
    State(state): State<AppState>,
    Json(body): Json<NameBody>,
) -> Result<Json<ShoppingList>, AppError> {
    let client = state.pool.get().await?;
    Ok(Json(shopping_lists::create(&client, &body.name).await?))
}

async fn delete_shopping_list(State(state): State<AppState>, Path(id): Path<i64>) -> Result<(), AppError> {
    let client = state.pool.get().await?;
    shopping_lists::delete(&client, id).await?;
    Ok(())
}

async fn update_shopping_list_name(
    State(state): State<AppState>,
    Path(id): Path<i64>,
    Json(body): Json<NameBody>,
) -> Result<Json<ShoppingList>, AppError> {
    let client = state.pool.get().await?;
    Ok(Json(shopping_lists::update_name(&client, id, &body.name).await?))
}
