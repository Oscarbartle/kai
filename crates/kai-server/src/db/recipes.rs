//! Postgres port of `src-tauri/src/db/recipes.rs`.

use chrono::{DateTime, Utc};
use deadpool_postgres::Client;
use kai_shared::recipes::Recipe;

const SELECT_COLUMNS: &str = "id, name, method, servings, source_url, image_url, created_at";

fn row_to_recipe(row: &tokio_postgres::Row) -> Recipe {
    Recipe {
        id: row.get(0),
        name: row.get(1),
        method: row.get(2),
        servings: row.get(3),
        source_url: row.get(4),
        image_url: row.get(5),
        created_at: row.get::<_, DateTime<Utc>>(6).to_rfc3339(),
    }
}

pub async fn create(client: &Client, name: &str) -> Result<Recipe, String> {
    let row = client
        .query_one(
            &format!("INSERT INTO recipes (name) VALUES ($1) RETURNING {SELECT_COLUMNS}"),
            &[&name],
        )
        .await
        .map_err(|e| format!("Couldn't create recipe: {e}"))?;
    Ok(row_to_recipe(&row))
}

pub async fn get(client: &Client, id: i64) -> Result<Recipe, String> {
    let row = client
        .query_opt(&format!("SELECT {SELECT_COLUMNS} FROM recipes WHERE id = $1"), &[&id])
        .await
        .map_err(|e| format!("Couldn't load recipe {id}: {e}"))?
        .ok_or_else(|| format!("No recipe with id {id}"))?;
    Ok(row_to_recipe(&row))
}

pub async fn update_name(client: &Client, id: i64, name: &str) -> Result<Recipe, String> {
    client
        .execute("UPDATE recipes SET name = $1 WHERE id = $2", &[&name, &id])
        .await
        .map_err(|e| format!("Couldn't update recipe {id}: {e}"))?;
    get(client, id).await
}

/// A single freeform method box, not individual steps — deliberately
/// simple.
pub async fn update_method(client: &Client, id: i64, method: &str) -> Result<Recipe, String> {
    client
        .execute("UPDATE recipes SET method = $1 WHERE id = $2", &[&method, &id])
        .await
        .map_err(|e| format!("Couldn't update recipe {id} method: {e}"))?;
    get(client, id).await
}

pub async fn update_servings(client: &Client, id: i64, servings: Option<i64>) -> Result<Recipe, String> {
    client
        .execute("UPDATE recipes SET servings = $1 WHERE id = $2", &[&servings, &id])
        .await
        .map_err(|e| format!("Couldn't update recipe {id} servings: {e}"))?;
    get(client, id).await
}

pub async fn update_source_url(client: &Client, id: i64, source_url: &str) -> Result<Recipe, String> {
    client
        .execute(
            "UPDATE recipes SET source_url = $1 WHERE id = $2",
            &[&source_url, &id],
        )
        .await
        .map_err(|e| format!("Couldn't update recipe {id} source url: {e}"))?;
    get(client, id).await
}

/// `image_url` empty/whitespace-only clears the override — same rule as
/// `items::set_image_url`.
pub async fn set_image_url(client: &Client, id: i64, image_url: Option<&str>) -> Result<Recipe, String> {
    let image_url = image_url.map(str::trim).filter(|s| !s.is_empty());
    client
        .execute("UPDATE recipes SET image_url = $1 WHERE id = $2", &[&image_url, &id])
        .await
        .map_err(|e| format!("Couldn't update recipe {id} image url: {e}"))?;
    get(client, id).await
}

pub async fn delete(client: &Client, id: i64) -> Result<(), String> {
    let changed = client
        .execute("DELETE FROM recipes WHERE id = $1", &[&id])
        .await
        .map_err(|e| format!("Couldn't delete recipe {id}: {e}"))?;
    if changed == 0 {
        return Err(format!("No recipe with id {id}"));
    }
    Ok(())
}

pub async fn list(client: &Client) -> Result<Vec<Recipe>, String> {
    let rows = client
        .query(
            &format!("SELECT {SELECT_COLUMNS} FROM recipes ORDER BY created_at DESC"),
            &[],
        )
        .await
        .map_err(|e| format!("Couldn't list recipes: {e}"))?;
    Ok(rows.iter().map(row_to_recipe).collect())
}
