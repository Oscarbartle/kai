use crate::db::items::Item;
use async_trait::async_trait;

/// Mirrors `db::items`' public functions (minus `&Connection`) one-for-one
/// with the `commands.rs` function that calls each — see `backend::mod`
/// for why this split exists. Method names match the command names
/// exactly where one exists, so `commands.rs`'s rewrite is close to
/// mechanical, and so combining every domain's trait into one `Backend`
/// can never collide on a method name.
#[async_trait]
pub trait ItemsBackend {
    async fn create_item(&self, name: &str) -> Result<Item, String>;
    async fn get_item(&self, id: i64) -> Result<Item, String>;
    async fn update_item_name(&self, id: i64, name: &str) -> Result<Item, String>;
    async fn set_item_perishable(&self, id: i64, is_perishable: bool) -> Result<Item, String>;
    async fn set_item_image_url(&self, id: i64, image_url: Option<&str>) -> Result<Item, String>;
    async fn set_item_cheapest_by(&self, id: i64, cheapest_by: &str) -> Result<Item, String>;
    async fn delete_item(&self, id: i64) -> Result<(), String>;
    async fn list_items(&self) -> Result<Vec<Item>, String>;
}
