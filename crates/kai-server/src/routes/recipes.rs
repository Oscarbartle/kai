use crate::db::recipes;
use crate::error::AppError;
use crate::state::AppState;
use axum::extract::{Path, State};
use axum::routing::{get, patch};
use axum::{Json, Router};
use kai_shared::recipes::Recipe;
use serde::Deserialize;

pub fn router() -> Router<AppState> {
    Router::new()
        .route("/recipes", get(list_recipes).post(create_recipe))
        .route("/recipes/{id}", axum::routing::delete(delete_recipe))
        .route("/recipes/{id}/name", patch(update_recipe_name))
        .route("/recipes/{id}/method", patch(update_recipe_method))
        .route("/recipes/{id}/servings", patch(update_recipe_servings))
        .route("/recipes/{id}/source-url", patch(update_recipe_source_url))
        .route("/recipes/{id}/image-url", patch(set_recipe_image_url))
}

async fn list_recipes(State(state): State<AppState>) -> Result<Json<Vec<Recipe>>, AppError> {
    let client = state.pool.get().await?;
    Ok(Json(recipes::list(&client).await?))
}

#[derive(Deserialize)]
struct NameBody {
    name: String,
}

async fn create_recipe(
    State(state): State<AppState>,
    Json(body): Json<NameBody>,
) -> Result<Json<Recipe>, AppError> {
    let client = state.pool.get().await?;
    Ok(Json(recipes::create(&client, &body.name).await?))
}

async fn delete_recipe(State(state): State<AppState>, Path(id): Path<i64>) -> Result<(), AppError> {
    let client = state.pool.get().await?;
    recipes::delete(&client, id).await?;
    Ok(())
}

async fn update_recipe_name(
    State(state): State<AppState>,
    Path(id): Path<i64>,
    Json(body): Json<NameBody>,
) -> Result<Json<Recipe>, AppError> {
    let client = state.pool.get().await?;
    Ok(Json(recipes::update_name(&client, id, &body.name).await?))
}

#[derive(Deserialize)]
struct MethodBody {
    method: String,
}

async fn update_recipe_method(
    State(state): State<AppState>,
    Path(id): Path<i64>,
    Json(body): Json<MethodBody>,
) -> Result<Json<Recipe>, AppError> {
    let client = state.pool.get().await?;
    Ok(Json(recipes::update_method(&client, id, &body.method).await?))
}

#[derive(Deserialize)]
struct ServingsBody {
    servings: Option<i64>,
}

async fn update_recipe_servings(
    State(state): State<AppState>,
    Path(id): Path<i64>,
    Json(body): Json<ServingsBody>,
) -> Result<Json<Recipe>, AppError> {
    let client = state.pool.get().await?;
    Ok(Json(recipes::update_servings(&client, id, body.servings).await?))
}

#[derive(Deserialize)]
struct SourceUrlBody {
    source_url: String,
}

async fn update_recipe_source_url(
    State(state): State<AppState>,
    Path(id): Path<i64>,
    Json(body): Json<SourceUrlBody>,
) -> Result<Json<Recipe>, AppError> {
    let client = state.pool.get().await?;
    Ok(Json(
        recipes::update_source_url(&client, id, &body.source_url).await?,
    ))
}

#[derive(Deserialize)]
struct ImageUrlBody {
    image_url: Option<String>,
}

async fn set_recipe_image_url(
    State(state): State<AppState>,
    Path(id): Path<i64>,
    Json(body): Json<ImageUrlBody>,
) -> Result<Json<Recipe>, AppError> {
    let client = state.pool.get().await?;
    Ok(Json(
        recipes::set_image_url(&client, id, body.image_url.as_deref()).await?,
    ))
}
