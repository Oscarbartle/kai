//! Postgres port of `src-tauri/src/db/shopping_lists.rs`.

use chrono::{DateTime, Utc};
use deadpool_postgres::Client;
use kai_shared::shopping_lists::ShoppingList;

fn row_to_list(row: &tokio_postgres::Row) -> ShoppingList {
    ShoppingList {
        id: row.get(0),
        name: row.get(1),
        created_at: row.get::<_, DateTime<Utc>>(2).to_rfc3339(),
    }
}

pub async fn create(client: &Client, name: &str) -> Result<ShoppingList, String> {
    let row = client
        .query_one(
            "INSERT INTO shopping_lists (name) VALUES ($1) RETURNING id, name, created_at",
            &[&name],
        )
        .await
        .map_err(|e| format!("Couldn't create shopping list: {e}"))?;
    Ok(row_to_list(&row))
}

pub async fn get(client: &Client, id: i64) -> Result<ShoppingList, String> {
    let row = client
        .query_opt("SELECT id, name, created_at FROM shopping_lists WHERE id = $1", &[&id])
        .await
        .map_err(|e| format!("Couldn't load shopping list {id}: {e}"))?
        .ok_or_else(|| format!("No shopping list with id {id}"))?;
    Ok(row_to_list(&row))
}

pub async fn update_name(client: &Client, id: i64, name: &str) -> Result<ShoppingList, String> {
    client
        .execute("UPDATE shopping_lists SET name = $1 WHERE id = $2", &[&name, &id])
        .await
        .map_err(|e| format!("Couldn't update shopping list {id}: {e}"))?;
    get(client, id).await
}

pub async fn delete(client: &Client, id: i64) -> Result<(), String> {
    let changed = client
        .execute("DELETE FROM shopping_lists WHERE id = $1", &[&id])
        .await
        .map_err(|e| format!("Couldn't delete shopping list {id}: {e}"))?;
    if changed == 0 {
        return Err(format!("No shopping list with id {id}"));
    }
    Ok(())
}

pub async fn list(client: &Client) -> Result<Vec<ShoppingList>, String> {
    let rows = client
        .query(
            "SELECT id, name, created_at FROM shopping_lists ORDER BY created_at DESC",
            &[],
        )
        .await
        .map_err(|e| format!("Couldn't list shopping lists: {e}"))?;
    Ok(rows.iter().map(row_to_list).collect())
}
