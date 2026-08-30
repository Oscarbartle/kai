//! Flat key-value store for small app-wide preferences — deliberately
//! generic rather than a dedicated typed column per setting, since
//! Settings.svelte is an explicitly growing container (see CLAUDE.md) and
//! most things that will land here are exactly this shape: one value, no
//! relations, changeable from one page.

use rusqlite::{params, Connection, OptionalExtension};

pub fn get(conn: &Connection, key: &str) -> Result<Option<String>, String> {
    conn.query_row("SELECT value FROM settings WHERE key = ?1", params![key], |row| {
        row.get(0)
    })
    .optional()
    .map_err(|e| format!("Couldn't read setting '{key}': {e}"))
}

pub fn set(conn: &Connection, key: &str, value: &str) -> Result<(), String> {
    conn.execute(
        "INSERT INTO settings (key, value) VALUES (?1, ?2)
         ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        params![key, value],
    )
    .map_err(|e| format!("Couldn't save setting '{key}': {e}"))?;
    Ok(())
}

// The flat fee Woolworths adds at checkout for delivery — not something
// their product/cart API exposes, so it's a user-entered constant rather
// than fetched data. Defaults to $14 (Oscar's stated usual fee) but
// changeable in Settings, since delivery pricing can vary by
// address/timeslot in reality.
pub const DELIVERY_FEE_KEY: &str = "delivery_fee";
pub const DEFAULT_DELIVERY_FEE: f64 = 14.0;

pub fn get_delivery_fee(conn: &Connection) -> Result<f64, String> {
    match get(conn, DELIVERY_FEE_KEY)? {
        Some(v) => v
            .parse::<f64>()
            .map_err(|e| format!("Stored delivery fee isn't a number: {e}")),
        None => Ok(DEFAULT_DELIVERY_FEE),
    }
}

pub fn set_delivery_fee(conn: &Connection, fee: f64) -> Result<f64, String> {
    if !fee.is_finite() || fee < 0.0 {
        return Err("Delivery fee must be a positive number".to_string());
    }
    set(conn, DELIVERY_FEE_KEY, &fee.to_string())?;
    Ok(fee)
}

// Which `Backend` (see src-tauri/src/backend/) the app should route
// through — local SQLite or a remote kai-server. Deliberately three plain
// keys in this same generic table rather than dedicated columns: these
// are meta-config about which backend to use, so (per CLAUDE.md's Phase B
// notes) they always live here, in the *local* connection, regardless of
// which backend is currently active — they can't live behind the thing
// they configure.
pub const BACKEND_MODE_KEY: &str = "backend_mode";
pub const REMOTE_URL_KEY: &str = "remote_url";
pub const REMOTE_TOKEN_KEY: &str = "remote_token";

#[derive(serde::Serialize, Clone, Debug)]
pub struct BackendConfig {
    /// `"local"` or `"remote"`.
    pub mode: String,
    pub remote_url: Option<String>,
    pub remote_token: Option<String>,
}

pub fn get_backend_config(conn: &Connection) -> Result<BackendConfig, String> {
    Ok(BackendConfig {
        mode: get(conn, BACKEND_MODE_KEY)?.unwrap_or_else(|| "local".to_string()),
        remote_url: get(conn, REMOTE_URL_KEY)?,
        remote_token: get(conn, REMOTE_TOKEN_KEY)?,
    })
}

pub fn set_backend_mode(conn: &Connection, mode: &str) -> Result<(), String> {
    if mode != "local" && mode != "remote" {
        return Err(format!("Invalid backend mode '{mode}' — must be 'local' or 'remote'"));
    }
    set(conn, BACKEND_MODE_KEY, mode)
}

pub fn set_remote_config(conn: &Connection, url: &str, token: &str) -> Result<(), String> {
    set(conn, REMOTE_URL_KEY, url)?;
    set(conn, REMOTE_TOKEN_KEY, token)?;
    Ok(())
}
