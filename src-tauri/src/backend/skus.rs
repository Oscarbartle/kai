use crate::db::skus::StoredSku;
use crate::woolworths::Sku;
use async_trait::async_trait;

#[async_trait]
pub trait SkusBackend {
    async fn save_sku_to_item(&self, item_id: i64, sku: &Sku) -> Result<StoredSku, String>;
    async fn get_sku(&self, id: i64) -> Result<StoredSku, String>;
    async fn list_skus_for_item(&self, item_id: i64) -> Result<Vec<StoredSku>, String>;
    async fn delete_sku(&self, id: i64) -> Result<(), String>;
    async fn set_sku_preferred(&self, id: i64, is_preferred: bool) -> Result<StoredSku, String>;
}
