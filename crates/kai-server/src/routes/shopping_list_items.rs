use crate::db::shopping_list_items;
use crate::error::AppError;
use crate::state::AppState;
use axum::extract::{Path, State};
use axum::routing::{get, patch};
use axum::{Json, Router};
use kai_shared::shopping_list_items::{OmissionReport, ShoppingListLine};
use serde::Deserialize;

pub fn router() -> Router<AppState> {
    Router::new()
        .route(
            "/shopping-lists/{list_id}/items",
            get(list_shopping_list_items).post(add_item_to_shopping_list),
        )
        .route("/shopping-lists/{list_id}/recipes", axum::routing::post(add_recipe_to_shopping_list))
        .route(
            "/shopping-lists/{list_id}/recipes/{recipe_id}/quantity",
            patch(set_shopping_list_recipe_quantity),
        )
        .route("/shopping-list-items/{id}/amount", patch(set_shopping_list_item_amount))
        .route("/shopping-list-items/{id}/sku", patch(set_shopping_list_item_sku))
        .route(
            "/shopping-list-items/{id}",
            axum::routing::delete(remove_shopping_list_item),
        )
        .route("/shopping-lists/omitted", axum::routing::post(list_omitted))
        .route("/items/{item_id}/cheapest-sku", get(cheapest_sku_id))
}

async fn list_shopping_list_items(
    State(state): State<AppState>,
    Path(list_id): Path<i64>,
) -> Result<Json<Vec<ShoppingListLine>>, AppError> {
    let client = state.pool.get().await?;
    Ok(Json(shopping_list_items::list_for_list(&client, list_id).await?))
}

#[derive(Deserialize)]
struct AddItemBody {
    item_id: i64,
    amount: Option<f64>,
    unit: Option<String>,
}

async fn add_item_to_shopping_list(
    State(state): State<AppState>,
    Path(list_id): Path<i64>,
    Json(body): Json<AddItemBody>,
) -> Result<Json<ShoppingListLine>, AppError> {
    let client = state.pool.get().await?;
    Ok(Json(
        shopping_list_items::add_item(
            &client,
            list_id,
            body.item_id,
            body.amount,
            body.unit.as_deref(),
            None,
        )
        .await?,
    ))
}

#[derive(Deserialize)]
struct AddRecipeBody {
    recipe_id: i64,
    target_servings: Option<i64>,
}

async fn add_recipe_to_shopping_list(
    State(state): State<AppState>,
    Path(list_id): Path<i64>,
    Json(body): Json<AddRecipeBody>,
) -> Result<Json<Vec<ShoppingListLine>>, AppError> {
    let client = state.pool.get().await?;
    Ok(Json(
        shopping_list_items::add_recipe(&client, list_id, body.recipe_id, body.target_servings).await?,
    ))
}

#[derive(Deserialize)]
struct QuantityBody {
    quantity: f64,
}

async fn set_shopping_list_recipe_quantity(
    State(state): State<AppState>,
    Path((list_id, recipe_id)): Path<(i64, i64)>,
    Json(body): Json<QuantityBody>,
) -> Result<Json<Vec<ShoppingListLine>>, AppError> {
    let client = state.pool.get().await?;
    Ok(Json(
        shopping_list_items::set_recipe_quantity(&client, list_id, recipe_id, body.quantity).await?,
    ))
}

#[derive(Deserialize)]
struct AmountBody {
    amount: Option<f64>,
    unit: Option<String>,
}

async fn set_shopping_list_item_amount(
    State(state): State<AppState>,
    Path(id): Path<i64>,
    Json(body): Json<AmountBody>,
) -> Result<Json<ShoppingListLine>, AppError> {
    let client = state.pool.get().await?;
    Ok(Json(
        shopping_list_items::set_amount(&client, id, body.amount, body.unit.as_deref()).await?,
    ))
}

#[derive(Deserialize)]
struct SkuBody {
    sku_id: Option<i64>,
}

async fn set_shopping_list_item_sku(
    State(state): State<AppState>,
    Path(id): Path<i64>,
    Json(body): Json<SkuBody>,
) -> Result<Json<ShoppingListLine>, AppError> {
    let client = state.pool.get().await?;
    Ok(Json(
        shopping_list_items::set_sku(&client, id, body.sku_id).await?,
    ))
}

async fn remove_shopping_list_item(State(state): State<AppState>, Path(id): Path<i64>) -> Result<(), AppError> {
    let client = state.pool.get().await?;
    shopping_list_items::remove(&client, id).await?;
    Ok(())
}

#[derive(Deserialize)]
struct OmittedBody {
    list_ids: Vec<i64>,
}

async fn list_omitted(
    State(state): State<AppState>,
    Json(body): Json<OmittedBody>,
) -> Result<Json<OmissionReport>, AppError> {
    let client = state.pool.get().await?;
    Ok(Json(
        shopping_list_items::list_omitted(&client, &body.list_ids).await?,
    ))
}

async fn cheapest_sku_id(
    State(state): State<AppState>,
    Path(item_id): Path<i64>,
) -> Result<Json<Option<i64>>, AppError> {
    let client = state.pool.get().await?;
    Ok(Json(
        shopping_list_items::cheapest_sku_id(&client, item_id).await?,
    ))
}
