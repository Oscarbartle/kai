use crate::db::{items, recipe_items};
use crate::error::AppError;
use crate::state::AppState;
use axum::extract::{Path, State};
use axum::routing::{get, patch};
use axum::{Json, Router};
use kai_shared::items::Item;
use serde::Deserialize;

pub fn router() -> Router<AppState> {
    Router::new()
        .route("/items", get(list_items).post(create_item))
        .route("/items/{id}", get(get_item).delete(delete_item))
        .route("/items/{id}/name", patch(update_item_name))
        .route("/items/{id}/perishable", patch(set_item_perishable))
        .route("/items/{id}/image-url", patch(set_item_image_url))
        .route("/items/{id}/cheapest-by", patch(set_item_cheapest_by))
        .route("/items/{id}/recipes", get(list_recipes_for_item))
}

async fn list_items(State(state): State<AppState>) -> Result<Json<Vec<Item>>, AppError> {
    let client = state.pool.get().await?;
    Ok(Json(items::list(&client).await?))
}

#[derive(Deserialize)]
struct CreateItem {
    name: String,
}

async fn create_item(
    State(state): State<AppState>,
    Json(body): Json<CreateItem>,
) -> Result<Json<Item>, AppError> {
    let client = state.pool.get().await?;
    Ok(Json(items::create(&client, &body.name).await?))
}

async fn get_item(State(state): State<AppState>, Path(id): Path<i64>) -> Result<Json<Item>, AppError> {
    let client = state.pool.get().await?;
    Ok(Json(items::get(&client, id).await?))
}

#[derive(Deserialize)]
struct NameBody {
    name: String,
}

async fn update_item_name(
    State(state): State<AppState>,
    Path(id): Path<i64>,
    Json(body): Json<NameBody>,
) -> Result<Json<Item>, AppError> {
    let client = state.pool.get().await?;
    Ok(Json(items::update_name(&client, id, &body.name).await?))
}

#[derive(Deserialize)]
struct PerishableBody {
    is_perishable: bool,
}

async fn set_item_perishable(
    State(state): State<AppState>,
    Path(id): Path<i64>,
    Json(body): Json<PerishableBody>,
) -> Result<Json<Item>, AppError> {
    let client = state.pool.get().await?;
    Ok(Json(items::set_perishable(&client, id, body.is_perishable).await?))
}

#[derive(Deserialize)]
struct ImageUrlBody {
    image_url: Option<String>,
}

async fn set_item_image_url(
    State(state): State<AppState>,
    Path(id): Path<i64>,
    Json(body): Json<ImageUrlBody>,
) -> Result<Json<Item>, AppError> {
    let client = state.pool.get().await?;
    Ok(Json(
        items::set_image_url(&client, id, body.image_url.as_deref()).await?,
    ))
}

#[derive(Deserialize)]
struct CheapestByBody {
    cheapest_by: String,
}

async fn set_item_cheapest_by(
    State(state): State<AppState>,
    Path(id): Path<i64>,
    Json(body): Json<CheapestByBody>,
) -> Result<Json<Item>, AppError> {
    let client = state.pool.get().await?;
    Ok(Json(
        items::set_cheapest_by(&client, id, &body.cheapest_by).await?,
    ))
}

/// Mirrors `commands::delete_item`'s guard exactly: an item still linked
/// to a recipe can't be deleted here either, same error message.
async fn delete_item(State(state): State<AppState>, Path(id): Path<i64>) -> Result<(), AppError> {
    let client = state.pool.get().await?;
    let recipes = recipe_items::list_recipes_for_item(&client, id).await?;
    if !recipes.is_empty() {
        return Err(AppError::bad_request(format!(
            "Can't delete — used in: {}. Remove it from those recipes first.",
            recipes.join(", ")
        )));
    }
    items::delete(&client, id).await?;
    Ok(())
}

async fn list_recipes_for_item(
    State(state): State<AppState>,
    Path(id): Path<i64>,
) -> Result<Json<Vec<String>>, AppError> {
    let client = state.pool.get().await?;
    Ok(Json(recipe_items::list_recipes_for_item(&client, id).await?))
}
