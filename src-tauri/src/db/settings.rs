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
