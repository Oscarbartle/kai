use crate::db::ingredient_aliases::IngredientAlias;
use async_trait::async_trait;

/// What the recipe importer has learned about this household's wording.
#[async_trait]
pub trait AliasesBackend {
    async fn list_ingredient_aliases(&self) -> Result<Vec<IngredientAlias>, String>;
    async fn set_ingredient_alias(&self, alias: &str, item_id: i64) -> Result<(), String>;
}
