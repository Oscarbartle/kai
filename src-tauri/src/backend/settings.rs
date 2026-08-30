use async_trait::async_trait;

/// Only the delivery fee — not the generic `db::settings::get/set` used
/// for backend-mode config itself, which deliberately always goes
/// straight to the local connection, never through `Backend` (see
/// `backend::mod` and CLAUDE.md's Phase B notes: it can't route through
/// the thing it configures).
#[async_trait]
pub trait SettingsBackend {
    async fn get_delivery_fee(&self) -> Result<f64, String>;
    async fn set_delivery_fee(&self, fee: f64) -> Result<f64, String>;
}
