//! Postgres port of `src-tauri/src/db/tags.rs`. `tags.name` is `CITEXT`
//! (see migrations/V1__init.sql) — plain `=` is already case-insensitive,
//! no `COLLATE NOCASE` equivalent needed in the queries themselves.

use deadpool_postgres::Client;
use kai_shared::tags::Tag;

fn row_to_tag(row: &tokio_postgres::Row) -> Tag {
    Tag {
        id: row.get(0),
        name: row.get(1),
        emoji: row.get(2),
    }
}

pub async fn list_all(client: &Client) -> Result<Vec<Tag>, String> {
    let rows = client
        .query("SELECT id, name, emoji FROM tags ORDER BY name", &[])
        .await
        .map_err(|e| format!("Couldn't list tags: {e}"))?;
    Ok(rows.iter().map(row_to_tag).collect())
}

pub async fn list_for_item(client: &Client, item_id: i64) -> Result<Vec<Tag>, String> {
    let rows = client
        .query(
            "SELECT tags.id, tags.name, tags.emoji
             FROM tags
             JOIN item_tags ON item_tags.tag_id = tags.id
             WHERE item_tags.item_id = $1
             ORDER BY tags.name",
            &[&item_id],
        )
        .await
        .map_err(|e| format!("Couldn't list tags for item {item_id}: {e}"))?;
    Ok(rows.iter().map(row_to_tag).collect())
}

async fn find_or_create(client: &Client, name: &str) -> Result<Tag, String> {
    let existing = client
        .query_opt("SELECT id, name, emoji FROM tags WHERE name = $1", &[&name])
        .await
        .map_err(|e| format!("Couldn't look up tag '{name}': {e}"))?;
    if let Some(row) = existing {
        return Ok(row_to_tag(&row));
    }
    let row = client
        .query_one(
            "INSERT INTO tags (name) VALUES ($1) RETURNING id, name, emoji",
            &[&name],
        )
        .await
        .map_err(|e| format!("Couldn't create tag '{name}': {e}"))?;
    Ok(row_to_tag(&row))
}

/// Tags an item with `name`, creating the tag if it doesn't already
/// exist (case-insensitively). Re-tagging with the same name is a no-op.
pub async fn add_to_item(client: &Client, item_id: i64, name: &str) -> Result<Tag, String> {
    let name = name.trim();
    if name.is_empty() {
        return Err("Tag name can't be empty".into());
    }
    let tag = find_or_create(client, name).await?;
    client
        .execute(
            "INSERT INTO item_tags (item_id, tag_id) VALUES ($1, $2) ON CONFLICT DO NOTHING",
            &[&item_id, &tag.id],
        )
        .await
        .map_err(|e| format!("Couldn't tag item {item_id} with '{name}': {e}"))?;
    Ok(tag)
}

pub async fn remove_from_item(client: &Client, item_id: i64, tag_id: i64) -> Result<(), String> {
    client
        .execute(
            "DELETE FROM item_tags WHERE item_id = $1 AND tag_id = $2",
            &[&item_id, &tag_id],
        )
        .await
        .map_err(|e| format!("Couldn't remove tag {tag_id} from item {item_id}: {e}"))?;
    Ok(())
}

/// Sets (or, with `None`, clears back to auto-picked) a tag's emoji
/// override — the Tags sidebar's "swap emoji" affordance.
pub async fn set_emoji(client: &Client, tag_id: i64, emoji: Option<&str>) -> Result<Tag, String> {
    let changed = client
        .execute("UPDATE tags SET emoji = $1 WHERE id = $2", &[&emoji, &tag_id])
        .await
        .map_err(|e| format!("Couldn't set emoji for tag {tag_id}: {e}"))?;
    if changed == 0 {
        return Err(format!("No tag with id {tag_id}"));
    }
    let row = client
        .query_one("SELECT id, name, emoji FROM tags WHERE id = $1", &[&tag_id])
        .await
        .map_err(|e| format!("Couldn't load tag {tag_id}: {e}"))?;
    Ok(row_to_tag(&row))
}

// --- Recipe tags — same `tags` table, a separate join table. ---

pub async fn list_for_recipe(client: &Client, recipe_id: i64) -> Result<Vec<Tag>, String> {
    let rows = client
        .query(
            "SELECT tags.id, tags.name, tags.emoji
             FROM tags
             JOIN recipe_tags ON recipe_tags.tag_id = tags.id
             WHERE recipe_tags.recipe_id = $1
             ORDER BY tags.name",
            &[&recipe_id],
        )
        .await
        .map_err(|e| format!("Couldn't list tags for recipe {recipe_id}: {e}"))?;
    Ok(rows.iter().map(row_to_tag).collect())
}

pub async fn add_to_recipe(client: &Client, recipe_id: i64, name: &str) -> Result<Tag, String> {
    let name = name.trim();
    if name.is_empty() {
        return Err("Tag name can't be empty".into());
    }
    let tag = find_or_create(client, name).await?;
    client
        .execute(
            "INSERT INTO recipe_tags (recipe_id, tag_id) VALUES ($1, $2) ON CONFLICT DO NOTHING",
            &[&recipe_id, &tag.id],
        )
        .await
        .map_err(|e| format!("Couldn't tag recipe {recipe_id} with '{name}': {e}"))?;
    Ok(tag)
}

pub async fn remove_from_recipe(client: &Client, recipe_id: i64, tag_id: i64) -> Result<(), String> {
    client
        .execute(
            "DELETE FROM recipe_tags WHERE recipe_id = $1 AND tag_id = $2",
            &[&recipe_id, &tag_id],
        )
        .await
        .map_err(|e| format!("Couldn't remove tag {tag_id} from recipe {recipe_id}: {e}"))?;
    Ok(())
}
