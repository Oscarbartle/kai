//! Postgres port of `src-tauri/src/db/recipe_items.rs`.

use deadpool_postgres::Client;
use kai_shared::recipe_items::{RecipeIngredient, VALID_UNITS};

fn validate_unit(unit: Option<&str>) -> Result<(), String> {
    match unit {
        None => Ok(()),
        Some(u) if VALID_UNITS.contains(&u) => Ok(()),
        Some(u) => Err(format!(
            "'{u}' isn't a recognised unit — use one of {VALID_UNITS:?}"
        )),
    }
}

/// Links an item to a recipe. Idempotent — adding the same item twice is
/// a no-op, not an error. No quantity set yet; use `set_quantity`.
pub async fn add(client: &Client, recipe_id: i64, item_id: i64) -> Result<(), String> {
    client
        .execute(
            "INSERT INTO recipe_items (recipe_id, item_id) VALUES ($1, $2) ON CONFLICT DO NOTHING",
            &[&recipe_id, &item_id],
        )
        .await
        .map_err(|e| format!("Couldn't add item {item_id} to recipe {recipe_id}: {e}"))?;
    Ok(())
}

pub async fn remove(client: &Client, recipe_id: i64, item_id: i64) -> Result<(), String> {
    client
        .execute(
            "DELETE FROM recipe_items WHERE recipe_id = $1 AND item_id = $2",
            &[&recipe_id, &item_id],
        )
        .await
        .map_err(|e| format!("Couldn't remove item {item_id} from recipe {recipe_id}: {e}"))?;
    Ok(())
}

async fn get_ingredient(client: &Client, recipe_id: i64, item_id: i64) -> Result<RecipeIngredient, String> {
    let row = client
        .query_one(
            "SELECT items.id, items.name, recipe_items.amount, recipe_items.unit
             FROM recipe_items
             JOIN items ON items.id = recipe_items.item_id
             WHERE recipe_items.recipe_id = $1 AND recipe_items.item_id = $2",
            &[&recipe_id, &item_id],
        )
        .await
        .map_err(|e| format!("Couldn't load recipe ingredient: {e}"))?;
    Ok(RecipeIngredient {
        item_id: row.get(0),
        name: row.get(1),
        amount: row.get(2),
        unit: row.get(3),
    })
}

pub async fn set_quantity(
    client: &Client,
    recipe_id: i64,
    item_id: i64,
    amount: Option<f64>,
    unit: Option<&str>,
) -> Result<RecipeIngredient, String> {
    validate_unit(unit)?;
    let changed = client
        .execute(
            "UPDATE recipe_items SET amount = $1, unit = $2
             WHERE recipe_id = $3 AND item_id = $4",
            &[&amount, &unit, &recipe_id, &item_id],
        )
        .await
        .map_err(|e| format!("Couldn't set quantity for item {item_id} on recipe {recipe_id}: {e}"))?;
    if changed == 0 {
        return Err(format!("Item {item_id} isn't linked to recipe {recipe_id}"));
    }
    get_ingredient(client, recipe_id, item_id).await
}

/// Names of every recipe that currently links this item — used to block
/// deleting an item that's still in use.
pub async fn list_recipes_for_item(client: &Client, item_id: i64) -> Result<Vec<String>, String> {
    let rows = client
        .query(
            "SELECT recipes.name
             FROM recipe_items
             JOIN recipes ON recipes.id = recipe_items.recipe_id
             WHERE recipe_items.item_id = $1
             ORDER BY recipes.name",
            &[&item_id],
        )
        .await
        .map_err(|e| format!("Couldn't list recipes using item {item_id}: {e}"))?;
    Ok(rows.iter().map(|row| row.get(0)).collect())
}

pub async fn list_for_recipe(client: &Client, recipe_id: i64) -> Result<Vec<RecipeIngredient>, String> {
    let rows = client
        .query(
            "SELECT items.id, items.name, recipe_items.amount, recipe_items.unit
             FROM recipe_items
             JOIN items ON items.id = recipe_items.item_id
             WHERE recipe_items.recipe_id = $1
             ORDER BY recipe_items.id ASC",
            &[&recipe_id],
        )
        .await
        .map_err(|e| format!("Couldn't list items for recipe {recipe_id}: {e}"))?;
    Ok(rows
        .iter()
        .map(|row| RecipeIngredient {
            item_id: row.get(0),
            name: row.get(1),
            amount: row.get(2),
            unit: row.get(3),
        })
        .collect())
}
