use rusqlite::{params, Connection, OptionalExtension};

// Tag moved to kai-shared (Phase B) — see crates/kai-shared/src/tags.rs.
pub use kai_shared::tags::{Tag, TagMembershipChanges};

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

fn get(conn: &Connection, tag_id: i64) -> Result<Tag, String> {
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
    .optional()
    .map_err(|e| format!("Couldn't load tag {tag_id}: {e}"))?
    .ok_or_else(|| format!("No tag with id {tag_id}"))
}

/// Renames a tag. Because a tag is one shared row, every item and recipe
/// that carries it shows the new name at once. A name that already
/// belongs to a *different* tag (case-insensitively) is refused rather
/// than merged; changing only the case of its own name is fine.
pub fn rename(conn: &Connection, tag_id: i64, name: &str) -> Result<Tag, String> {
    let name = name.trim();
    if name.is_empty() {
        return Err("Tag name can't be empty".into());
    }
    get(conn, tag_id)?;
    let clash: Option<i64> = conn
        .query_row(
            "SELECT id FROM tags WHERE name = ?1 COLLATE NOCASE AND id != ?2",
            params![name, tag_id],
            |row| row.get(0),
        )
        .optional()
        .map_err(|e| format!("Couldn't check for an existing tag '{name}': {e}"))?;
    if clash.is_some() {
        return Err(format!("A tag called '{name}' already exists"));
    }
    conn.execute(
        "UPDATE tags SET name = ?1 WHERE id = ?2",
        params![name, tag_id],
    )
    .map_err(|e| format!("Couldn't rename tag {tag_id}: {e}"))?;
    get(conn, tag_id)
}

/// Applies a batch of tag/untag changes in one transaction — all of it or
/// none of it.
pub fn apply_membership_changes(
    conn: &Connection,
    tag_id: i64,
    changes: &TagMembershipChanges,
) -> Result<(), String> {
    get(conn, tag_id)?;
    let tx = conn
        .unchecked_transaction()
        .map_err(|e| format!("Couldn't start tag update: {e}"))?;
    for item_id in &changes.remove_item_ids {
        tx.execute(
            "DELETE FROM item_tags WHERE item_id = ?1 AND tag_id = ?2",
            params![item_id, tag_id],
        )
        .map_err(|e| format!("Couldn't remove tag {tag_id} from item {item_id}: {e}"))?;
    }
    for recipe_id in &changes.remove_recipe_ids {
        tx.execute(
            "DELETE FROM recipe_tags WHERE recipe_id = ?1 AND tag_id = ?2",
            params![recipe_id, tag_id],
        )
        .map_err(|e| format!("Couldn't remove tag {tag_id} from recipe {recipe_id}: {e}"))?;
    }
    for item_id in &changes.add_item_ids {
        tx.execute(
            "INSERT OR IGNORE INTO item_tags (item_id, tag_id) VALUES (?1, ?2)",
            params![item_id, tag_id],
        )
        .map_err(|e| format!("Couldn't tag item {item_id}: {e}"))?;
    }
    for recipe_id in &changes.add_recipe_ids {
        tx.execute(
            "INSERT OR IGNORE INTO recipe_tags (recipe_id, tag_id) VALUES (?1, ?2)",
            params![recipe_id, tag_id],
        )
        .map_err(|e| format!("Couldn't tag recipe {recipe_id}: {e}"))?;
    }
    tx.commit()
        .map_err(|e| format!("Couldn't save tag changes: {e}"))
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::db::{items, recipes};

    fn conn() -> Connection {
        let mut conn = Connection::open_in_memory().unwrap();
        conn.pragma_update(None, "foreign_keys", true).unwrap();
        crate::db::migrations().to_latest(&mut conn).unwrap();
        conn
    }

    #[test]
    fn rename_shows_everywhere_and_refuses_a_clash() {
        let conn = conn();
        let onion = items::create(&conn, "Onion").unwrap();
        let soup = recipes::create(&conn, "Soup").unwrap();
        let veg = add_to_item(&conn, onion.id, "Veg").unwrap();
        add_to_recipe(&conn, soup.id, "Veg").unwrap();
        let other = add_to_item(&conn, onion.id, "Vegetable").unwrap();

        // Case-only change of its own name is allowed.
        assert_eq!(rename(&conn, veg.id, "VEG").unwrap().name, "VEG");

        // Clash with a different tag, in any case, is refused and changes nothing.
        let err = rename(&conn, veg.id, " vegetable ").unwrap_err();
        assert!(err.contains("already exists"), "{err}");
        assert_eq!(list_for_recipe(&conn, soup.id).unwrap()[0].name, "VEG");

        assert!(rename(&conn, veg.id, "   ").is_err());

        // A real rename is seen by both the item and the recipe.
        rename(&conn, veg.id, "Greens").unwrap();
        assert!(list_for_item(&conn, onion.id).unwrap().iter().any(|t| t.name == "Greens"));
        assert_eq!(list_for_recipe(&conn, soup.id).unwrap()[0].name, "Greens");
        assert_ne!(veg.id, other.id);
    }

    #[test]
    fn membership_changes_apply_the_difference_atomically() {
        let conn = conn();
        let a = items::create(&conn, "A").unwrap();
        let b = items::create(&conn, "B").unwrap();
        let c = items::create(&conn, "C").unwrap();
        let soup = recipes::create(&conn, "Soup").unwrap();
        let tag = add_to_item(&conn, a.id, "Quick").unwrap();
        add_to_item(&conn, b.id, "Quick").unwrap();

        apply_membership_changes(
            &conn,
            tag.id,
            &TagMembershipChanges {
                add_item_ids: vec![c.id, b.id], // b is already tagged: fine
                remove_item_ids: vec![a.id],
                add_recipe_ids: vec![soup.id],
                remove_recipe_ids: vec![],
            },
        )
        .unwrap();
        let has = |id| list_for_item(&conn, id).unwrap().iter().any(|t| t.id == tag.id);
        assert!(!has(a.id) && has(b.id) && has(c.id));
        assert_eq!(list_for_recipe(&conn, soup.id).unwrap().len(), 1);

        // One bad id rolls the whole batch back: `a` must not be re-tagged.
        let err = apply_membership_changes(
            &conn,
            tag.id,
            &TagMembershipChanges {
                add_item_ids: vec![a.id, 9999],
                ..Default::default()
            },
        );
        assert!(err.is_err());
        assert!(!has(a.id));

        assert!(apply_membership_changes(&conn, 9999, &TagMembershipChanges::default()).is_err());
    }
}
