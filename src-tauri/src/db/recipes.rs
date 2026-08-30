use rusqlite::{params, Connection};

// Recipe moved to kai-shared (Phase B) — see crates/kai-shared/src/recipes.rs.
pub use kai_shared::recipes::Recipe;

const SELECT_COLUMNS: &str = "id, name, method, servings, source_url, image_url, created_at";

fn row_to_recipe(row: &rusqlite::Row) -> rusqlite::Result<Recipe> {
    Ok(Recipe {
        id: row.get(0)?,
        name: row.get(1)?,
        method: row.get(2)?,
        servings: row.get(3)?,
        source_url: row.get(4)?,
        image_url: row.get(5)?,
        created_at: row.get(6)?,
    })
}

pub fn create(conn: &Connection, name: &str) -> Result<Recipe, String> {
    conn.execute("INSERT INTO recipes (name) VALUES (?1)", params![name])
        .map_err(|e| format!("Couldn't create recipe: {e}"))?;
    let id = conn.last_insert_rowid();
    get(conn, id)
}

pub fn get(conn: &Connection, id: i64) -> Result<Recipe, String> {
    conn.query_row(
        &format!("SELECT {SELECT_COLUMNS} FROM recipes WHERE id = ?1"),
        params![id],
        row_to_recipe,
    )
    .map_err(|e| format!("Couldn't load recipe {id}: {e}"))
}

pub fn update_name(conn: &Connection, id: i64, name: &str) -> Result<Recipe, String> {
    conn.execute(
        "UPDATE recipes SET name = ?1 WHERE id = ?2",
        params![name, id],
    )
    .map_err(|e| format!("Couldn't update recipe {id}: {e}"))?;
    get(conn, id)
}

/// A single freeform method box, not individual steps — deliberately
/// simple. `method` is nullable/empty when nothing's been written yet.
pub fn update_method(conn: &Connection, id: i64, method: &str) -> Result<Recipe, String> {
    conn.execute(
        "UPDATE recipes SET method = ?1 WHERE id = ?2",
        params![method, id],
    )
    .map_err(|e| format!("Couldn't update recipe {id} method: {e}"))?;
    get(conn, id)
}

pub fn update_servings(conn: &Connection, id: i64, servings: Option<i64>) -> Result<Recipe, String> {
    conn.execute(
        "UPDATE recipes SET servings = ?1 WHERE id = ?2",
        params![servings, id],
    )
    .map_err(|e| format!("Couldn't update recipe {id} servings: {e}"))?;
    get(conn, id)
}

pub fn update_source_url(conn: &Connection, id: i64, source_url: &str) -> Result<Recipe, String> {
    conn.execute(
        "UPDATE recipes SET source_url = ?1 WHERE id = ?2",
        params![source_url, id],
    )
    .map_err(|e| format!("Couldn't update recipe {id} source url: {e}"))?;
    get(conn, id)
}

/// `image_url` empty/whitespace-only clears the override — same rule as
/// `items::set_image_url`.
pub fn set_image_url(conn: &Connection, id: i64, image_url: Option<&str>) -> Result<Recipe, String> {
    let image_url = image_url.map(str::trim).filter(|s| !s.is_empty());
    conn.execute(
        "UPDATE recipes SET image_url = ?1 WHERE id = ?2",
        params![image_url, id],
    )
    .map_err(|e| format!("Couldn't update recipe {id} image url: {e}"))?;
    get(conn, id)
}

pub fn delete(conn: &Connection, id: i64) -> Result<(), String> {
    let changed = conn
        .execute("DELETE FROM recipes WHERE id = ?1", params![id])
        .map_err(|e| format!("Couldn't delete recipe {id}: {e}"))?;
    if changed == 0 {
        return Err(format!("No recipe with id {id}"));
    }
    Ok(())
}

pub fn list(conn: &Connection) -> Result<Vec<Recipe>, String> {
    let mut stmt = conn
        .prepare(&format!(
            "SELECT {SELECT_COLUMNS} FROM recipes ORDER BY created_at DESC"
        ))
        .map_err(|e| format!("Couldn't prepare recipe list query: {e}"))?;

    let rows = stmt
        .query_map([], row_to_recipe)
        .map_err(|e| format!("Couldn't list recipes: {e}"))?;

    rows.collect::<Result<Vec<_>, _>>()
        .map_err(|e| format!("Couldn't read recipe rows: {e}"))
}
