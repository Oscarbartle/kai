use rusqlite::{params, Connection};

// Item/VALID_CHEAPEST_BY moved to kai-shared (Phase B: shared wire shape
// between local SQLite and a future remote server) — see
// crates/kai-shared/src/items.rs.
pub use kai_shared::items::{Item, VALID_CHEAPEST_BY};

const SELECT_COLUMNS: &str = "id, name, is_perishable, image_url, cheapest_by, created_at";

fn row_to_item(row: &rusqlite::Row) -> rusqlite::Result<Item> {
    Ok(Item {
        id: row.get(0)?,
        name: row.get(1)?,
        is_perishable: row.get(2)?,
        image_url: row.get(3)?,
        cheapest_by: row.get(4)?,
        created_at: row.get(5)?,
    })
}

pub fn create(conn: &Connection, name: &str) -> Result<Item, String> {
    conn.execute("INSERT INTO items (name) VALUES (?1)", params![name])
        .map_err(|e| format!("Couldn't create item: {e}"))?;
    let id = conn.last_insert_rowid();
    get(conn, id)
}

pub fn get(conn: &Connection, id: i64) -> Result<Item, String> {
    conn.query_row(
        &format!("SELECT {SELECT_COLUMNS} FROM items WHERE id = ?1"),
        params![id],
        row_to_item,
    )
    .map_err(|e| format!("Couldn't load item {id}: {e}"))
}

pub fn update_name(conn: &Connection, id: i64, name: &str) -> Result<Item, String> {
    conn.execute(
        "UPDATE items SET name = ?1 WHERE id = ?2",
        params![name, id],
    )
    .map_err(|e| format!("Couldn't update item {id}: {e}"))?;
    get(conn, id)
}

pub fn set_perishable(conn: &Connection, id: i64, is_perishable: bool) -> Result<Item, String> {
    conn.execute(
        "UPDATE items SET is_perishable = ?1 WHERE id = ?2",
        params![is_perishable, id],
    )
    .map_err(|e| format!("Couldn't update item {id}: {e}"))?;
    get(conn, id)
}

/// `image_url` empty/whitespace-only clears the override back to the
/// SKU-image fallback rather than storing a blank string.
pub fn set_image_url(conn: &Connection, id: i64, image_url: Option<&str>) -> Result<Item, String> {
    let image_url = image_url.map(str::trim).filter(|s| !s.is_empty());
    conn.execute(
        "UPDATE items SET image_url = ?1 WHERE id = ?2",
        params![image_url, id],
    )
    .map_err(|e| format!("Couldn't update item {id}: {e}"))?;
    get(conn, id)
}

pub fn set_cheapest_by(conn: &Connection, id: i64, cheapest_by: &str) -> Result<Item, String> {
    if !VALID_CHEAPEST_BY.contains(&cheapest_by) {
        return Err(format!(
            "'{cheapest_by}' isn't a recognised cheapest-by option — use one of {VALID_CHEAPEST_BY:?}"
        ));
    }
    conn.execute(
        "UPDATE items SET cheapest_by = ?1 WHERE id = ?2",
        params![cheapest_by, id],
    )
    .map_err(|e| format!("Couldn't update item {id}: {e}"))?;
    get(conn, id)
}

/// Deletes an item and, via the `ON DELETE CASCADE` on `skus.item_id`,
/// all its linked SKUs with it.
pub fn delete(conn: &Connection, id: i64) -> Result<(), String> {
    let changed = conn
        .execute("DELETE FROM items WHERE id = ?1", params![id])
        .map_err(|e| format!("Couldn't delete item {id}: {e}"))?;
    if changed == 0 {
        return Err(format!("No item with id {id}"));
    }
    Ok(())
}

pub fn list(conn: &Connection) -> Result<Vec<Item>, String> {
    // Alphabetical (case-insensitive), not insertion order — this is the
    // one query every item list in the app draws from (Pantry grid, the
    // drag-and-drop sidebars in Recipe/Shopping List detail views), so
    // fixing the order here fixes it everywhere at once.
    let mut stmt = conn
        .prepare(&format!(
            "SELECT {SELECT_COLUMNS} FROM items ORDER BY name COLLATE NOCASE ASC"
        ))
        .map_err(|e| format!("Couldn't prepare item list query: {e}"))?;

    let rows = stmt
        .query_map([], row_to_item)
        .map_err(|e| format!("Couldn't list items: {e}"))?;

    rows.collect::<Result<Vec<_>, _>>()
        .map_err(|e| format!("Couldn't read item rows: {e}"))
}
