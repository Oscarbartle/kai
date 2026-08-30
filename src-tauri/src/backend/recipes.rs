use crate::db::recipes::Recipe;
use async_trait::async_trait;

#[async_trait]
pub trait RecipesBackend {
    async fn create_recipe(&self, name: &str) -> Result<Recipe, String>;
    async fn list_recipes(&self) -> Result<Vec<Recipe>, String>;
    async fn update_recipe_name(&self, id: i64, name: &str) -> Result<Recipe, String>;
    async fn set_recipe_image_url(&self, id: i64, image_url: Option<&str>) -> Result<Recipe, String>;
    async fn delete_recipe(&self, id: i64) -> Result<(), String>;
    async fn update_recipe_method(&self, id: i64, method: &str) -> Result<Recipe, String>;
    async fn update_recipe_servings(&self, id: i64, servings: Option<i64>) -> Result<Recipe, String>;
    async fn update_recipe_source_url(&self, id: i64, source_url: &str) -> Result<Recipe, String>;
}
