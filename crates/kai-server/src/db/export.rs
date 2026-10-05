//! Reads every table out as JSON, for the backup export.
//!
//! Postgres does the row-to-JSON conversion itself (`to_jsonb`), so each
//! column comes out under its real name with its real type — numbers as
//! numbers, timestamps as RFC 3339 strings, the JSONB `images` /
//! `allergens` / `ingredients` columns as the arrays they are — and this
//! file never has to know a table's columns. A new column in a future
//! migration is exported automatically; only a new *table* needs adding to
//! `TABLES`.
//!
//! All tables are read inside one `REPEATABLE READ` read-only transaction,
//! so the backup is a single consistent snapshot even if someone is
//! editing while it runs — a shopping-list line can't appear in the
//! export pointing at an item that was deleted a moment earlier.

use deadpool_postgres::Client;
use serde_json::Value;
use tokio_postgres::IsolationLevel;

/// `(table, ORDER BY)` — every table in the database, each with a stable
/// order so two exports of unchanged data are byte-identical. Join tables
/// have no `id`, so they sort on their key columns.
pub const TABLES: &[(&str, &str)] = &[
    ("items", "t.id"),
    ("skus", "t.id"),
    ("tags", "t.id"),
    ("item_tags", "t.item_id, t.tag_id"),
    ("recipes", "t.id"),
    ("recipe_items", "t.id"),
    ("recipe_tags", "t.recipe_id, t.tag_id"),
    ("shopping_lists", "t.id"),
    ("shopping_list_items", "t.id"),
    ("settings", "t.key"),
];

pub struct TableDump {
    pub name: &'static str,
    pub rows: Vec<Value>,
}

pub async fn dump_all(client: &mut Client) -> Result<Vec<TableDump>, String> {
    let tx = client
        .build_transaction()
        .isolation_level(IsolationLevel::RepeatableRead)
        .read_only(true)
        .start()
        .await
        .map_err(|e| format!("Couldn't start the export snapshot: {e}"))?;

    let mut out = Vec::with_capacity(TABLES.len());
    for (name, order) in TABLES {
        // Table and ORDER BY are the constants above, never user input.
        let row = tx
            .query_one(
                &format!(
                    "SELECT COALESCE(jsonb_agg(to_jsonb(t) ORDER BY {order}), '[]'::jsonb) FROM {name} t"
                ),
                &[],
            )
            .await
            .map_err(|e| format!("Couldn't read table {name} for the export: {e}"))?;
        let rows = match row.get::<_, Value>(0) {
            Value::Array(rows) => rows,
            other => return Err(format!("Table {name} exported as {other}, not a list")),
        };
        out.push(TableDump { name, rows });
    }

    tx.commit()
        .await
        .map_err(|e| format!("Couldn't finish the export snapshot: {e}"))?;
    Ok(out)
}
