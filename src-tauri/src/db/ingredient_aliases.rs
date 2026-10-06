use rusqlite::{params, Connection};

pub use kai_shared::ingredient_aliases::IngredientAlias;

pub fn list(conn: &Connection) -> Result<Vec<IngredientAlias>, String> {
    let mut stmt = conn
        .prepare("SELECT alias, item_id FROM ingredient_aliases ORDER BY alias")
        .map_err(|e| format!("Couldn't prepare the alias list query: {e}"))?;
    let rows = stmt
        .query_map([], |row| {
            Ok(IngredientAlias {
                alias: row.get(0)?,
                item_id: row.get(1)?,
            })
        })
        .map_err(|e| format!("Couldn't list aliases: {e}"))?;
    rows.collect::<Result<Vec<_>, _>>()
        .map_err(|e| format!("Couldn't read alias rows: {e}"))
}

/// Remembers (or, for an alias already known, changes) which item it means.
/// A later choice replaces an earlier one, which is how a wrong alias gets
/// corrected: just pick the right item next time.
pub fn set(conn: &Connection, alias: &str, item_id: i64) -> Result<(), String> {
    let alias = alias.trim().to_lowercase();
    if alias.is_empty() {
        return Err("An alias can't be empty".into());
    }
    conn.execute(
        "INSERT INTO ingredient_aliases (alias, item_id) VALUES (?1, ?2)
         ON CONFLICT(alias) DO UPDATE SET item_id = excluded.item_id",
        params![alias, item_id],
    )
    .map_err(|e| format!("Couldn't remember that match: {e}"))?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::db::items;

    fn conn() -> Connection {
        let mut conn = Connection::open_in_memory().unwrap();
        conn.pragma_update(None, "foreign_keys", true).unwrap();
        crate::db::migrations().to_latest(&mut conn).unwrap();
        conn
    }

    #[test]
    fn remembers_replaces_and_forgets_with_the_item() {
        let conn = conn();
        let onion = items::create(&conn, "Brown Onion").unwrap();
        let red = items::create(&conn, "Red Onion").unwrap();

        set(&conn, "  Onion  ", onion.id).unwrap();
        assert_eq!(list(&conn).unwrap(), vec![IngredientAlias { alias: "onion".into(), item_id: onion.id }]);

        // The same alias in another case is the same alias; the newer choice wins.
        set(&conn, "ONION", red.id).unwrap();
        let aliases = list(&conn).unwrap();
        assert_eq!(aliases.len(), 1);
        assert_eq!(aliases[0].item_id, red.id);

        // Deleting the item takes its aliases with it — no dangling ids.
        items::delete(&conn, red.id).unwrap();
        assert!(list(&conn).unwrap().is_empty());
    }

    #[test]
    fn refuses_an_empty_alias_and_an_unknown_item() {
        let conn = conn();
        assert!(set(&conn, "   ", 1).unwrap_err().contains("can't be empty"));
        assert!(set(&conn, "onion", 9999).is_err(), "an alias must point at a real item");
        assert!(list(&conn).unwrap().is_empty());
    }
}
