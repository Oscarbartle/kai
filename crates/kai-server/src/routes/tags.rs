use crate::db::tags;
use crate::error::AppError;
use crate::state::AppState;
use axum::extract::{Path, State};
use axum::routing::{get, patch};
use axum::{Json, Router};
use kai_shared::tags::Tag;
use serde::Deserialize;

pub fn router() -> Router<AppState> {
    Router::new()
        .route("/tags", get(list_tags))
        .route("/items/{item_id}/tags", get(list_tags_for_item).post(add_tag_to_item))
        .route("/items/{item_id}/tags/{tag_id}", axum::routing::delete(remove_tag_from_item))
        .route("/tags/{id}/emoji", patch(set_tag_emoji))
        .route(
            "/recipes/{recipe_id}/tags",
            get(list_tags_for_recipe).post(add_tag_to_recipe),
        )
        .route(
            "/recipes/{recipe_id}/tags/{tag_id}",
            axum::routing::delete(remove_tag_from_recipe),
        )
}

async fn list_tags(State(state): State<AppState>) -> Result<Json<Vec<Tag>>, AppError> {
    let client = state.pool.get().await?;
    Ok(Json(tags::list_all(&client).await?))
}

async fn list_tags_for_item(
    State(state): State<AppState>,
    Path(item_id): Path<i64>,
) -> Result<Json<Vec<Tag>>, AppError> {
    let client = state.pool.get().await?;
    Ok(Json(tags::list_for_item(&client, item_id).await?))
}

#[derive(Deserialize)]
struct NameBody {
    name: String,
}

async fn add_tag_to_item(
    State(state): State<AppState>,
    Path(item_id): Path<i64>,
    Json(body): Json<NameBody>,
) -> Result<Json<Tag>, AppError> {
    let client = state.pool.get().await?;
    Ok(Json(tags::add_to_item(&client, item_id, &body.name).await?))
}

async fn remove_tag_from_item(
    State(state): State<AppState>,
    Path((item_id, tag_id)): Path<(i64, i64)>,
) -> Result<(), AppError> {
    let client = state.pool.get().await?;
    tags::remove_from_item(&client, item_id, tag_id).await?;
    Ok(())
}

#[derive(Deserialize)]
struct EmojiBody {
    emoji: Option<String>,
}

async fn set_tag_emoji(
    State(state): State<AppState>,
    Path(id): Path<i64>,
    Json(body): Json<EmojiBody>,
) -> Result<Json<Tag>, AppError> {
    let client = state.pool.get().await?;
    Ok(Json(tags::set_emoji(&client, id, body.emoji.as_deref()).await?))
}

async fn list_tags_for_recipe(
    State(state): State<AppState>,
    Path(recipe_id): Path<i64>,
) -> Result<Json<Vec<Tag>>, AppError> {
    let client = state.pool.get().await?;
    Ok(Json(tags::list_for_recipe(&client, recipe_id).await?))
}

async fn add_tag_to_recipe(
    State(state): State<AppState>,
    Path(recipe_id): Path<i64>,
    Json(body): Json<NameBody>,
) -> Result<Json<Tag>, AppError> {
    let client = state.pool.get().await?;
    Ok(Json(tags::add_to_recipe(&client, recipe_id, &body.name).await?))
}

async fn remove_tag_from_recipe(
    State(state): State<AppState>,
    Path((recipe_id, tag_id)): Path<(i64, i64)>,
) -> Result<(), AppError> {
    let client = state.pool.get().await?;
    tags::remove_from_recipe(&client, recipe_id, tag_id).await?;
    Ok(())
}
