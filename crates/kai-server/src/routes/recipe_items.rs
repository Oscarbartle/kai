use crate::db::recipe_items;
use crate::error::AppError;
use crate::state::AppState;
use axum::extract::{Path, State};
use axum::routing::{get, patch};
use axum::{Json, Router};
use kai_shared::recipe_items::RecipeIngredient;
use serde::Deserialize;

pub fn router() -> Router<AppState> {
    Router::new()
        .route("/recipes/{recipe_id}/items", axum::routing::post(add_item_to_recipe))
        .route(
            "/recipes/{recipe_id}/items/{item_id}",
            axum::routing::delete(remove_item_from_recipe),
        )
        .route("/recipes/{recipe_id}/ingredients", get(list_recipe_ingredients))
        .route(
            "/recipes/{recipe_id}/items/{item_id}/quantity",
            patch(set_recipe_item_quantity),
        )
}

#[derive(Deserialize)]
struct ItemIdBody {
    item_id: i64,
}

async fn add_item_to_recipe(
    State(state): State<AppState>,
    Path(recipe_id): Path<i64>,
    Json(body): Json<ItemIdBody>,
) -> Result<(), AppError> {
    let client = state.pool.get().await?;
    recipe_items::add(&client, recipe_id, body.item_id).await?;
    Ok(())
}

async fn remove_item_from_recipe(
    State(state): State<AppState>,
    Path((recipe_id, item_id)): Path<(i64, i64)>,
) -> Result<(), AppError> {
    let client = state.pool.get().await?;
    recipe_items::remove(&client, recipe_id, item_id).await?;
    Ok(())
}

async fn list_recipe_ingredients(
    State(state): State<AppState>,
    Path(recipe_id): Path<i64>,
) -> Result<Json<Vec<RecipeIngredient>>, AppError> {
    let client = state.pool.get().await?;
    Ok(Json(recipe_items::list_for_recipe(&client, recipe_id).await?))
}

#[derive(Deserialize)]
struct QuantityBody {
    amount: Option<f64>,
    unit: Option<String>,
}

async fn set_recipe_item_quantity(
    State(state): State<AppState>,
    Path((recipe_id, item_id)): Path<(i64, i64)>,
    Json(body): Json<QuantityBody>,
) -> Result<Json<RecipeIngredient>, AppError> {
    let client = state.pool.get().await?;
    Ok(Json(
        recipe_items::set_quantity(&client, recipe_id, item_id, body.amount, body.unit.as_deref()).await?,
    ))
}
