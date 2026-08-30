//! Postgres port of `src-tauri/src/db/settings.rs` — only the delivery
//! fee is exposed remotely; backend-mode config itself never leaves the
//! device it's set on (see CLAUDE.md's Phase B notes).

use deadpool_postgres::Client;

pub const DELIVERY_FEE_KEY: &str = "delivery_fee";
pub const DEFAULT_DELIVERY_FEE: f64 = 14.0;

async fn get(client: &Client, key: &str) -> Result<Option<String>, String> {
    Ok(client
        .query_opt("SELECT value FROM settings WHERE key = $1", &[&key])
        .await
        .map_err(|e| format!("Couldn't read setting '{key}': {e}"))?
        .map(|row| row.get(0)))
}

async fn set(client: &Client, key: &str, value: &str) -> Result<(), String> {
    client
        .execute(
            "INSERT INTO settings (key, value) VALUES ($1, $2)
             ON CONFLICT (key) DO UPDATE SET value = excluded.value",
            &[&key, &value],
        )
        .await
        .map_err(|e| format!("Couldn't save setting '{key}': {e}"))?;
    Ok(())
}

pub async fn get_delivery_fee(client: &Client) -> Result<f64, String> {
    match get(client, DELIVERY_FEE_KEY).await? {
        Some(v) => v
            .parse::<f64>()
            .map_err(|e| format!("Stored delivery fee isn't a number: {e}")),
        None => Ok(DEFAULT_DELIVERY_FEE),
    }
}

pub async fn set_delivery_fee(client: &Client, fee: f64) -> Result<f64, String> {
    if !fee.is_finite() || fee < 0.0 {
        return Err("Delivery fee must be a positive number".to_string());
    }
    set(client, DELIVERY_FEE_KEY, &fee.to_string()).await?;
    Ok(fee)
}
