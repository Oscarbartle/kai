use crate::db::shopping_list_items::{OmissionReport, ShoppingListLine};
use async_trait::async_trait;

#[async_trait]
pub trait ShoppingListItemsBackend {
    async fn list_shopping_list_items(&self, list_id: i64) -> Result<Vec<ShoppingListLine>, String>;
    async fn list_omitted_shopping_list_items(
        &self,
        list_ids: &[i64],
    ) -> Result<OmissionReport, String>;
    async fn add_item_to_shopping_list(
        &self,
        list_id: i64,
        item_id: i64,
        amount: Option<f64>,
        unit: Option<&str>,
    ) -> Result<ShoppingListLine, String>;
    async fn add_recipe_to_shopping_list(
        &self,
        list_id: i64,
        recipe_id: i64,
        target_servings: Option<i64>,
    ) -> Result<Vec<ShoppingListLine>, String>;
    async fn set_shopping_list_recipe_quantity(
        &self,
        list_id: i64,
        recipe_id: i64,
        quantity: f64,
    ) -> Result<Vec<ShoppingListLine>, String>;
    async fn set_shopping_list_item_amount(
        &self,
        line_id: i64,
        amount: Option<f64>,
        unit: Option<&str>,
    ) -> Result<ShoppingListLine, String>;
    async fn set_shopping_list_item_sku(
        &self,
        line_id: i64,
        sku_id: Option<i64>,
    ) -> Result<ShoppingListLine, String>;
    async fn remove_shopping_list_item(&self, line_id: i64) -> Result<(), String>;
    /// Used directly by `add_shopping_lists_to_cart` to resolve a SKU for
    /// an omission-check "extra item" the same way a fresh item-drop
    /// would — see `db::shopping_list_items::cheapest_sku_id`.
    async fn cheapest_sku_id(&self, item_id: i64) -> Result<Option<i64>, String>;
}
