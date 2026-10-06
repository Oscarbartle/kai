use crate::db::ingredient_aliases;
use crate::error::AppError;
use crate::state::AppState;
use axum::extract::State;
use axum::routing::get;
use axum::{Json, Router};
use kai_shared::ingredient_aliases::IngredientAlias;

pub fn router() -> Router<AppState> {
    Router::new().route("/ingredient-aliases", get(list_aliases).post(set_alias))
}

async fn list_aliases(State(state): State<AppState>) -> Result<Json<Vec<IngredientAlias>>, AppError> {
    let client = state.pool.get().await?;
    Ok(Json(ingredient_aliases::list(&client).await?))
}

async fn set_alias(
    State(state): State<AppState>,
    Json(body): Json<IngredientAlias>,
) -> Result<(), AppError> {
    let client = state.pool.get().await?;
    ingredient_aliases::set(&client, &body.alias, body.item_id).await?;
    Ok(())
}
