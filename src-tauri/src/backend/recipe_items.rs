use crate::db::recipe_items::RecipeIngredient;
use async_trait::async_trait;

#[async_trait]
pub trait RecipeItemsBackend {
    async fn add_item_to_recipe(&self, recipe_id: i64, item_id: i64) -> Result<(), String>;
    async fn remove_item_from_recipe(&self, recipe_id: i64, item_id: i64) -> Result<(), String>;
    async fn list_recipe_ingredients(&self, recipe_id: i64) -> Result<Vec<RecipeIngredient>, String>;
    async fn set_recipe_item_quantity(
        &self,
        recipe_id: i64,
        item_id: i64,
        amount: Option<f64>,
        unit: Option<&str>,
    ) -> Result<RecipeIngredient, String>;
    /// Guards `delete_item` — an item still linked to a recipe can't be
    /// deleted, and the guard needs the recipe names to say which ones.
    async fn list_recipes_for_item(&self, item_id: i64) -> Result<Vec<String>, String>;
}
