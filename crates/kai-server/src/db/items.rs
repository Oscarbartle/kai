//! Postgres port of `src-tauri/src/db/items.rs` — same rules, same error
//! messages where possible, different SQL (see CLAUDE.md's Phase B
//! dialect notes: `RETURNING id` instead of `last_insert_rowid()`, native
//! `BOOLEAN`, `TIMESTAMPTZ`).

use chrono::{DateTime, Utc};
use deadpool_postgres::Client;
use kai_shared::items::Item;
pub use kai_shared::items::VALID_CHEAPEST_BY;

const SELECT_COLUMNS: &str = "id, name, is_perishable, image_url, cheapest_by, created_at";

fn row_to_item(row: &tokio_postgres::Row) -> Item {
    Item {
        id: row.get(0),
        name: row.get(1),
        is_perishable: row.get(2),
        image_url: row.get(3),
        cheapest_by: row.get(4),
        created_at: row.get::<_, DateTime<Utc>>(5).to_rfc3339(),
    }
}

pub async fn create(client: &Client, name: &str) -> Result<Item, String> {
    let row = client
        .query_one(
            &format!("INSERT INTO items (name) VALUES ($1) RETURNING {SELECT_COLUMNS}"),
            &[&name],
        )
        .await
        .map_err(|e| format!("Couldn't create item: {e}"))?;
    Ok(row_to_item(&row))
}

pub async fn get(client: &Client, id: i64) -> Result<Item, String> {
    let row = client
        .query_opt(&format!("SELECT {SELECT_COLUMNS} FROM items WHERE id = $1"), &[&id])
        .await
        .map_err(|e| format!("Couldn't load item {id}: {e}"))?
        .ok_or_else(|| format!("No item with id {id}"))?;
    Ok(row_to_item(&row))
}

pub async fn update_name(client: &Client, id: i64, name: &str) -> Result<Item, String> {
    let changed = client
        .execute("UPDATE items SET name = $1 WHERE id = $2", &[&name, &id])
        .await
        .map_err(|e| format!("Couldn't update item {id}: {e}"))?;
    if changed == 0 {
        return Err(format!("No item with id {id}"));
    }
    get(client, id).await
}

pub async fn set_perishable(client: &Client, id: i64, is_perishable: bool) -> Result<Item, String> {
    client
        .execute(
            "UPDATE items SET is_perishable = $1 WHERE id = $2",
            &[&is_perishable, &id],
        )
        .await
        .map_err(|e| format!("Couldn't update item {id}: {e}"))?;
    get(client, id).await
}

/// `image_url` empty/whitespace-only clears the override back to the
/// SKU-image fallback rather than storing a blank string.
pub async fn set_image_url(client: &Client, id: i64, image_url: Option<&str>) -> Result<Item, String> {
    let image_url = image_url.map(str::trim).filter(|s| !s.is_empty());
    client
        .execute("UPDATE items SET image_url = $1 WHERE id = $2", &[&image_url, &id])
        .await
        .map_err(|e| format!("Couldn't update item {id}: {e}"))?;
    get(client, id).await
}

pub async fn set_cheapest_by(client: &Client, id: i64, cheapest_by: &str) -> Result<Item, String> {
    if !VALID_CHEAPEST_BY.contains(&cheapest_by) {
        return Err(format!(
            "'{cheapest_by}' isn't a recognised cheapest-by option — use one of {VALID_CHEAPEST_BY:?}"
        ));
    }
    client
        .execute(
            "UPDATE items SET cheapest_by = $1 WHERE id = $2",
            &[&cheapest_by, &id],
        )
        .await
        .map_err(|e| format!("Couldn't update item {id}: {e}"))?;
    get(client, id).await
}

/// Deletes an item and, via the `ON DELETE CASCADE` on `skus.item_id`,
/// all its linked SKUs with it.
pub async fn delete(client: &Client, id: i64) -> Result<(), String> {
    let changed = client
        .execute("DELETE FROM items WHERE id = $1", &[&id])
        .await
        .map_err(|e| format!("Couldn't delete item {id}: {e}"))?;
    if changed == 0 {
        return Err(format!("No item with id {id}"));
    }
    Ok(())
}

pub async fn list(client: &Client) -> Result<Vec<Item>, String> {
    let rows = client
        .query(
            &format!("SELECT {SELECT_COLUMNS} FROM items ORDER BY created_at DESC"),
            &[],
        )
        .await
        .map_err(|e| format!("Couldn't list items: {e}"))?;
    Ok(rows.iter().map(row_to_item).collect())
}
