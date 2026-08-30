use rusqlite::{params, Connection};

// RecipeIngredient/VALID_UNITS moved to kai-shared (Phase B) — see
// crates/kai-shared/src/recipe_items.rs.
pub use kai_shared::recipe_items::{RecipeIngredient, VALID_UNITS};

fn validate_unit(unit: Option<&str>) -> Result<(), String> {
    match unit {
        None => Ok(()),
        Some(u) if VALID_UNITS.contains(&u) => Ok(()),
        Some(u) => Err(format!(
            "'{u}' isn't a recognised unit — use one of {VALID_UNITS:?}"
        )),
    }
}

/// Links an item to a recipe. Idempotent — adding the same item twice
/// is a no-op, not an error. No quantity set yet; use `set_quantity`.
pub fn add(conn: &Connection, recipe_id: i64, item_id: i64) -> Result<(), String> {
    conn.execute(
        "INSERT OR IGNORE INTO recipe_items (recipe_id, item_id) VALUES (?1, ?2)",
        params![recipe_id, item_id],
    )
    .map_err(|e| format!("Couldn't add item {item_id} to recipe {recipe_id}: {e}"))?;
    Ok(())
}

pub fn remove(conn: &Connection, recipe_id: i64, item_id: i64) -> Result<(), String> {
    conn.execute(
        "DELETE FROM recipe_items WHERE recipe_id = ?1 AND item_id = ?2",
        params![recipe_id, item_id],
    )
    .map_err(|e| format!("Couldn't remove item {item_id} from recipe {recipe_id}: {e}"))?;
    Ok(())
}

pub fn set_quantity(
    conn: &Connection,
    recipe_id: i64,
    item_id: i64,
    amount: Option<f64>,
    unit: Option<&str>,
) -> Result<RecipeIngredient, String> {
    validate_unit(unit)?;
    let changed = conn
        .execute(
            "UPDATE recipe_items SET amount = ?1, unit = ?2
             WHERE recipe_id = ?3 AND item_id = ?4",
            params![amount, unit, recipe_id, item_id],
        )
        .map_err(|e| format!("Couldn't set quantity for item {item_id} on recipe {recipe_id}: {e}"))?;
    if changed == 0 {
        return Err(format!(
            "Item {item_id} isn't linked to recipe {recipe_id}"
        ));
    }
    get(conn, recipe_id, item_id)
}

fn get(conn: &Connection, recipe_id: i64, item_id: i64) -> Result<RecipeIngredient, String> {
    conn.query_row(
        "SELECT items.id, items.name, recipe_items.amount, recipe_items.unit
         FROM recipe_items
         JOIN items ON items.id = recipe_items.item_id
         WHERE recipe_items.recipe_id = ?1 AND recipe_items.item_id = ?2",
        params![recipe_id, item_id],
        |row| {
            Ok(RecipeIngredient {
                item_id: row.get(0)?,
                name: row.get(1)?,
                amount: row.get(2)?,
                unit: row.get(3)?,
            })
        },
    )
    .map_err(|e| format!("Couldn't load recipe ingredient: {e}"))
}

/// Names of every recipe that currently links this item — used to block
/// deleting an item that's still in use rather than silently cascading
/// the link away (see CLAUDE.md: items in a recipe you have to remove
/// it from first, not a surprise disappearance).
pub fn list_recipes_for_item(conn: &Connection, item_id: i64) -> Result<Vec<String>, String> {
    let mut stmt = conn
        .prepare(
            "SELECT recipes.name
             FROM recipe_items
             JOIN recipes ON recipes.id = recipe_items.recipe_id
             WHERE recipe_items.item_id = ?1
             ORDER BY recipes.name COLLATE NOCASE",
        )
        .map_err(|e| format!("Couldn't prepare recipe-usage query: {e}"))?;

    let rows = stmt
        .query_map(params![item_id], |row| row.get::<_, String>(0))
        .map_err(|e| format!("Couldn't list recipes using item {item_id}: {e}"))?;

    rows.collect::<Result<Vec<_>, _>>()
        .map_err(|e| format!("Couldn't read recipe-usage rows: {e}"))
}

pub fn list_for_recipe(conn: &Connection, recipe_id: i64) -> Result<Vec<RecipeIngredient>, String> {
    let mut stmt = conn
        .prepare(
            "SELECT items.id, items.name, recipe_items.amount, recipe_items.unit
             FROM recipe_items
             JOIN items ON items.id = recipe_items.item_id
             WHERE recipe_items.recipe_id = ?1
             ORDER BY recipe_items.rowid ASC",
        )
        .map_err(|e| format!("Couldn't prepare recipe item query: {e}"))?;

    let rows = stmt
        .query_map(params![recipe_id], |row| {
            Ok(RecipeIngredient {
                item_id: row.get(0)?,
                name: row.get(1)?,
                amount: row.get(2)?,
                unit: row.get(3)?,
            })
        })
        .map_err(|e| format!("Couldn't list items for recipe {recipe_id}: {e}"))?;

    rows.collect::<Result<Vec<_>, _>>()
        .map_err(|e| format!("Couldn't read recipe item rows: {e}"))
}
