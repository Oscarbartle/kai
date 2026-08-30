use rusqlite::{params, Connection};

// ShoppingList moved to kai-shared (Phase B) — see
// crates/kai-shared/src/shopping_lists.rs.
pub use kai_shared::shopping_lists::ShoppingList;

pub fn create(conn: &Connection, name: &str) -> Result<ShoppingList, String> {
    conn.execute("INSERT INTO shopping_lists (name) VALUES (?1)", params![name])
        .map_err(|e| format!("Couldn't create shopping list: {e}"))?;
    let id = conn.last_insert_rowid();
    get(conn, id)
}

pub fn get(conn: &Connection, id: i64) -> Result<ShoppingList, String> {
    conn.query_row(
        "SELECT id, name, created_at FROM shopping_lists WHERE id = ?1",
        params![id],
        |row| {
            Ok(ShoppingList {
                id: row.get(0)?,
                name: row.get(1)?,
                created_at: row.get(2)?,
            })
        },
    )
    .map_err(|e| format!("Couldn't load shopping list {id}: {e}"))
}

pub fn update_name(conn: &Connection, id: i64, name: &str) -> Result<ShoppingList, String> {
    conn.execute(
        "UPDATE shopping_lists SET name = ?1 WHERE id = ?2",
        params![name, id],
    )
    .map_err(|e| format!("Couldn't update shopping list {id}: {e}"))?;
    get(conn, id)
}

pub fn delete(conn: &Connection, id: i64) -> Result<(), String> {
    let changed = conn
        .execute("DELETE FROM shopping_lists WHERE id = ?1", params![id])
        .map_err(|e| format!("Couldn't delete shopping list {id}: {e}"))?;
    if changed == 0 {
        return Err(format!("No shopping list with id {id}"));
    }
    Ok(())
}

pub fn list(conn: &Connection) -> Result<Vec<ShoppingList>, String> {
    let mut stmt = conn
        .prepare("SELECT id, name, created_at FROM shopping_lists ORDER BY created_at DESC")
        .map_err(|e| format!("Couldn't prepare shopping list query: {e}"))?;

    let rows = stmt
        .query_map([], |row| {
            Ok(ShoppingList {
                id: row.get(0)?,
                name: row.get(1)?,
                created_at: row.get(2)?,
            })
        })
        .map_err(|e| format!("Couldn't list shopping lists: {e}"))?;

    rows.collect::<Result<Vec<_>, _>>()
        .map_err(|e| format!("Couldn't read shopping list rows: {e}"))
}
