//! Postgres port of `src-tauri/src/db/ingredient_aliases.rs`.
//! `alias` is `CITEXT`, so uniqueness and `ON CONFLICT` are already
//! case-insensitive.

use deadpool_postgres::Client;
use kai_shared::ingredient_aliases::IngredientAlias;

pub async fn list(client: &Client) -> Result<Vec<IngredientAlias>, String> {
    let rows = client
        .query("SELECT alias::text, item_id FROM ingredient_aliases ORDER BY alias", &[])
        .await
        .map_err(|e| format!("Couldn't list aliases: {e}"))?;
    Ok(rows
        .iter()
        .map(|row| IngredientAlias {
            alias: row.get(0),
            item_id: row.get(1),
        })
        .collect())
}

pub async fn set(client: &Client, alias: &str, item_id: i64) -> Result<(), String> {
    let alias = alias.trim().to_lowercase();
    if alias.is_empty() {
        return Err("An alias can't be empty".into());
    }
    client
        .execute(
            "INSERT INTO ingredient_aliases (alias, item_id) VALUES ($1, $2)
             ON CONFLICT (alias) DO UPDATE SET item_id = EXCLUDED.item_id",
            &[&alias, &item_id],
        )
        .await
        .map_err(|e| format!("Couldn't remember that match: {e}"))?;
    Ok(())
}
