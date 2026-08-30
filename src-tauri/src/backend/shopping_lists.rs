use crate::db::shopping_lists::ShoppingList;
use async_trait::async_trait;

#[async_trait]
pub trait ShoppingListsBackend {
    async fn create_shopping_list(&self, name: &str) -> Result<ShoppingList, String>;
    async fn list_shopping_lists(&self) -> Result<Vec<ShoppingList>, String>;
    async fn update_shopping_list_name(&self, id: i64, name: &str) -> Result<ShoppingList, String>;
    async fn delete_shopping_list(&self, id: i64) -> Result<(), String>;
}
