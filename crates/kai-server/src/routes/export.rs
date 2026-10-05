//! `GET /export` — the whole database as a zip, for backups.
//!
//! The zip holds `manifest.json` plus one `<table>.json` per table (see
//! `db::export` for what is in them). Original ids are kept, so every
//! relationship — which items carry which tags, which lines belong to
//! which list — survives and the data could be loaded back into a fresh
//! database. There is deliberately no restore route: overwriting live
//! data is a separate, much riskier feature than reading it.
//!
//! Contains no secrets: the shared token lives in the server's
//! environment, not in the database, and images are just URLs.

use crate::db::export::{self, TableDump};
use crate::error::AppError;
use crate::state::AppState;
use axum::http::header;
use axum::response::IntoResponse;
use axum::routing::get;
use axum::{extract::State, Router};
use chrono::Utc;
use serde_json::{json, Map, Value};
use std::io::{Cursor, Write};
use zip::write::SimpleFileOptions;
use zip::{CompressionMethod, ZipWriter};

pub fn router() -> Router<AppState> {
    Router::new().route("/export", get(export_backup))
}

async fn export_backup(State(state): State<AppState>) -> Result<impl IntoResponse, AppError> {
    let mut client = state.pool.get().await?;
    let tables = export::dump_all(&mut client).await?;
    drop(client);

    let now = Utc::now();
    let bytes = build_zip(&tables, &now.to_rfc3339()).map_err(AppError::internal)?;
    // The desktop app names the file it saves with its own local time;
    // this name only matters to a browser or curl.
    let filename = format!("kai-backup-{}.zip", now.format("%Y-%m-%d_%H-%M-%S"));
    Ok((
        [
            (header::CONTENT_TYPE, "application/zip".to_string()),
            (
                header::CONTENT_DISPOSITION,
                format!("attachment; filename=\"{filename}\""),
            ),
            // A backup must never be answered from a cache.
            (header::CACHE_CONTROL, "no-store".to_string()),
        ],
        bytes,
    ))
}

/// Builds the zip in memory — the whole database is a few MB at most
/// (every row is short text, images are links), so streaming would be
/// complexity for nothing.
pub fn build_zip(tables: &[TableDump], exported_at: &str) -> Result<Vec<u8>, String> {
    let mut counts = Map::new();
    for t in tables {
        counts.insert(t.name.to_string(), Value::from(t.rows.len()));
    }
    let manifest = json!({
        "format": 1,
        "exported_at": exported_at,
        "server_version": env!("CARGO_PKG_VERSION"),
        "about": "Each <table>.json is a list of that table's rows as stored, original ids included.",
        "row_counts": counts,
    });

    let mut zip = ZipWriter::new(Cursor::new(Vec::new()));
    let options = SimpleFileOptions::default().compression_method(CompressionMethod::Deflated);

    let mut add = |name: String, value: &Value| -> Result<(), String> {
        let body = serde_json::to_vec_pretty(value).map_err(|e| format!("Couldn't write {name}: {e}"))?;
        zip.start_file(&name, options)
            .map_err(|e| format!("Couldn't add {name} to the zip: {e}"))?;
        zip.write_all(&body)
            .map_err(|e| format!("Couldn't write {name} into the zip: {e}"))
    };

    add("manifest.json".into(), &manifest)?;
    for t in tables {
        add(format!("{}.json", t.name), &Value::Array(t.rows.clone()))?;
    }

    Ok(zip
        .finish()
        .map_err(|e| format!("Couldn't finish the zip: {e}"))?
        .into_inner())
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::Read;

    #[test]
    fn zip_has_a_manifest_and_a_file_per_table() {
        let tables = vec![
            TableDump { name: "items", rows: vec![json!({"id": 1, "name": "Onion"})] },
            TableDump { name: "tags", rows: vec![] },
        ];
        let bytes = build_zip(&tables, "2026-10-06T00:00:00Z").unwrap();
        let mut archive = zip::ZipArchive::new(Cursor::new(bytes)).unwrap();
        let mut names: Vec<_> = archive.file_names().map(String::from).collect();
        names.sort();
        assert_eq!(names, ["items.json", "manifest.json", "tags.json"]);

        let mut read = |name: &str| {
            let mut s = String::new();
            archive.by_name(name).unwrap().read_to_string(&mut s).unwrap();
            serde_json::from_str::<Value>(&s).unwrap()
        };
        let manifest = read("manifest.json");
        assert_eq!(manifest["row_counts"]["items"], 1);
        assert_eq!(manifest["row_counts"]["tags"], 0);
        assert_eq!(manifest["exported_at"], "2026-10-06T00:00:00Z");
        assert_eq!(read("items.json")[0]["name"], "Onion");
        assert_eq!(read("tags.json"), json!([]));
    }
}
