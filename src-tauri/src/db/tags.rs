use rusqlite::{params, Connection, OptionalExtension};
use serde::Serialize;

#[derive(Serialize, Clone, Debug)]
pub struct Tag {
    pub id: i64,
    pub name: String,
    /// User override for the sidebar toggle's emoji — `None` means "use
    /// the auto-picked one" (a client-side guess off the name, see
    /// +page.svelte). Never shown on the plain-text tag pills.
    pub emoji: Option<String>,
}

/// All tags that exist, regardless of what they're attached to — for
/// reuse/autocomplete when tagging an item.
pub fn list_all(conn: &Connection) -> Result<Vec<Tag>, String> {
    let mut stmt = conn
        .prepare("SELECT id, name, emoji FROM tags ORDER BY name COLLATE NOCASE")
        .map_err(|e| format!("Couldn't prepare tag list query: {e}"))?;

    let rows = stmt
        .query_map([], |row| {
            Ok(Tag {
                id: row.get(0)?,
                name: row.get(1)?,
                emoji: row.get(2)?,
            })
        })
        .map_err(|e| format!("Couldn't list tags: {e}"))?;

    rows.collect::<Result<Vec<_>, _>>()
        .map_err(|e| format!("Couldn't read tag rows: {e}"))
}

pub fn list_for_item(conn: &Connection, item_id: i64) -> Result<Vec<Tag>, String> {
    let mut stmt = conn
        .prepare(
            "SELECT tags.id, tags.name, tags.emoji
             FROM tags
             JOIN item_tags ON item_tags.tag_id = tags.id
             WHERE item_tags.item_id = ?1
             ORDER BY tags.name COLLATE NOCASE",
        )
        .map_err(|e| format!("Couldn't prepare item tag query: {e}"))?;

    let rows = stmt
        .query_map(params![item_id], |row| {
            Ok(Tag {
                id: row.get(0)?,
                name: row.get(1)?,
                emoji: row.get(2)?,
            })
        })
        .map_err(|e| format!("Couldn't list tags for item {item_id}: {e}"))?;

    rows.collect::<Result<Vec<_>, _>>()
        .map_err(|e| format!("Couldn't read item tag rows: {e}"))
}

/// Sets (or, with `None`, clears back to auto-picked) a tag's emoji
/// override — the Tags sidebar's "swap emoji" affordance.
pub fn set_emoji(conn: &Connection, tag_id: i64, emoji: Option<&str>) -> Result<Tag, String> {
    conn.execute(
        "UPDATE tags SET emoji = ?1 WHERE id = ?2",
        params![emoji, tag_id],
    )
    .map_err(|e| format!("Couldn't set emoji for tag {tag_id}: {e}"))?;
    conn.query_row(
        "SELECT id, name, emoji FROM tags WHERE id = ?1",
        params![tag_id],
        |row| {
            Ok(Tag {
                id: row.get(0)?,
                name: row.get(1)?,
                emoji: row.get(2)?,
            })
        },
    )
    .map_err(|e| format!("Couldn't load tag {tag_id}: {e}"))
}

fn find_or_create(conn: &Connection, name: &str) -> Result<Tag, String> {
    let existing = conn
        .query_row(
            "SELECT id, name, emoji FROM tags WHERE name = ?1 COLLATE NOCASE",
            params![name],
            |row| {
                Ok(Tag {
                    id: row.get(0)?,
                    name: row.get(1)?,
                    emoji: row.get(2)?,
                })
            },
        )
        .optional()
        .map_err(|e| format!("Couldn't look up tag '{name}': {e}"))?;

    if let Some(tag) = existing {
        return Ok(tag);
    }

    conn.execute("INSERT INTO tags (name) VALUES (?1)", params![name])
        .map_err(|e| format!("Couldn't create tag '{name}': {e}"))?;
    let id = conn.last_insert_rowid();
    Ok(Tag {
        id,
        name: name.to_string(),
        emoji: None,
    })
}

/// Tags an item with `name`, creating the tag if it doesn't already
/// exist (case-insensitively). Re-tagging with the same name is a no-op.
pub fn add_to_item(conn: &Connection, item_id: i64, name: &str) -> Result<Tag, String> {
    let name = name.trim();
    if name.is_empty() {
        return Err("Tag name can't be empty".into());
    }
    let tag = find_or_create(conn, name)?;
    conn.execute(
        "INSERT OR IGNORE INTO item_tags (item_id, tag_id) VALUES (?1, ?2)",
        params![item_id, tag.id],
    )
    .map_err(|e| format!("Couldn't tag item {item_id} with '{name}': {e}"))?;
    Ok(tag)
}

/// Unlinks a tag from an item. The tag itself stays around (it may be
/// used by other items) — this only removes the association.
pub fn remove_from_item(conn: &Connection, item_id: i64, tag_id: i64) -> Result<(), String> {
    conn.execute(
        "DELETE FROM item_tags WHERE item_id = ?1 AND tag_id = ?2",
        params![item_id, tag_id],
    )
    .map_err(|e| format!("Couldn't remove tag {tag_id} from item {item_id}: {e}"))?;
    Ok(())
}

// --- Recipe tags — same `tags` table, a separate join table. ---

pub fn list_for_recipe(conn: &Connection, recipe_id: i64) -> Result<Vec<Tag>, String> {
    let mut stmt = conn
        .prepare(
            "SELECT tags.id, tags.name, tags.emoji
             FROM tags
             JOIN recipe_tags ON recipe_tags.tag_id = tags.id
             WHERE recipe_tags.recipe_id = ?1
             ORDER BY tags.name COLLATE NOCASE",
        )
        .map_err(|e| format!("Couldn't prepare recipe tag query: {e}"))?;

    let rows = stmt
        .query_map(params![recipe_id], |row| {
            Ok(Tag {
                id: row.get(0)?,
                name: row.get(1)?,
                emoji: row.get(2)?,
            })
        })
        .map_err(|e| format!("Couldn't list tags for recipe {recipe_id}: {e}"))?;

    rows.collect::<Result<Vec<_>, _>>()
        .map_err(|e| format!("Couldn't read recipe tag rows: {e}"))
}

pub fn add_to_recipe(conn: &Connection, recipe_id: i64, name: &str) -> Result<Tag, String> {
    let name = name.trim();
    if name.is_empty() {
        return Err("Tag name can't be empty".into());
    }
    let tag = find_or_create(conn, name)?;
    conn.execute(
        "INSERT OR IGNORE INTO recipe_tags (recipe_id, tag_id) VALUES (?1, ?2)",
        params![recipe_id, tag.id],
    )
    .map_err(|e| format!("Couldn't tag recipe {recipe_id} with '{name}': {e}"))?;
    Ok(tag)
}

pub fn remove_from_recipe(conn: &Connection, recipe_id: i64, tag_id: i64) -> Result<(), String> {
    conn.execute(
        "DELETE FROM recipe_tags WHERE recipe_id = ?1 AND tag_id = ?2",
        params![recipe_id, tag_id],
    )
    .map_err(|e| format!("Couldn't remove tag {tag_id} from recipe {recipe_id}: {e}"))?;
    Ok(())
}
