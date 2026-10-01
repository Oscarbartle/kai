//! Bulk read endpoints for thin clients (the mobile web app) — one request
//! per screen instead of one per item.
//!
//! Why these exist at all: a pantry card needs its SKUs (image, price) and
//! its tags, and the per-resource routes would make a phone do roughly
//! `2 × number of items` requests to draw the list (180 for a 90-item
//! pantry) over a cellular connection and a Cloudflare tunnel. The same
//! N+1 happens here, but against a database on the same box, where it
//! costs microseconds rather than round trips over the internet.
//!
//! Deliberately composed from the existing `db::*` functions rather than
//! new SQL — these are a convenience over what's already there, not a
//! second source of truth for how anything is read. Read-only.
//!
//! Also what makes an offline cache cheap later: each screen's data is one
//! JSON document.

use crate::db::{items, recipe_items, recipes, skus, tags};
use crate::error::AppError;
use crate::state::AppState;
use axum::extract::State;
use axum::routing::get;
use axum::{Json, Router};
use kai_shared::items::Item;
use kai_shared::recipe_items::RecipeIngredient;
use kai_shared::recipes::Recipe;
use kai_shared::skus::StoredSku;
use kai_shared::tags::Tag;
use serde::Serialize;

pub fn router() -> Router<AppState> {
    Router::new()
        .route("/pantry", get(pantry))
        .route("/recipe-book", get(recipe_book))
}

/// Everything a pantry card shows: the item, its linked SKUs (for the
/// image and cheapest price) and its tags (for filtering). Mirrors the
/// desktop's own `ItemCard` shape.
#[derive(Serialize)]
struct PantryEntry {
    item: Item,
    skus: Vec<StoredSku>,
    tags: Vec<Tag>,
}

/// Everything a recipe card shows, ingredients included, so opening one
/// needs no further request.
#[derive(Serialize)]
struct RecipeBookEntry {
    recipe: Recipe,
    tags: Vec<Tag>,
    ingredients: Vec<RecipeIngredient>,
}

async fn pantry(State(state): State<AppState>) -> Result<Json<Vec<PantryEntry>>, AppError> {
    let client = state.pool.get().await?;
    let mut out = Vec::new();
    // `items::list` is already alphabetical (case-insensitive).
    for item in items::list(&client).await? {
        let skus = skus::list_for_item(&client, item.id).await?;
        let tags = tags::list_for_item(&client, item.id).await?;
        out.push(PantryEntry { item, skus, tags });
    }
    Ok(Json(out))
}

async fn recipe_book(State(state): State<AppState>) -> Result<Json<Vec<RecipeBookEntry>>, AppError> {
    let client = state.pool.get().await?;
    let mut out = Vec::new();
    for recipe in recipes::list(&client).await? {
        let tags = tags::list_for_recipe(&client, recipe.id).await?;
        let ingredients = recipe_items::list_for_recipe(&client, recipe.id).await?;
        out.push(RecipeBookEntry { recipe, tags, ingredients });
    }
    Ok(Json(out))
}
