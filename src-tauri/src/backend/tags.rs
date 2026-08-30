use crate::db::tags::Tag;
use async_trait::async_trait;

#[async_trait]
pub trait TagsBackend {
    async fn list_tags(&self) -> Result<Vec<Tag>, String>;
    async fn list_tags_for_item(&self, item_id: i64) -> Result<Vec<Tag>, String>;
    async fn add_tag_to_item(&self, item_id: i64, name: &str) -> Result<Tag, String>;
    async fn remove_tag_from_item(&self, item_id: i64, tag_id: i64) -> Result<(), String>;
    async fn set_tag_emoji(&self, tag_id: i64, emoji: Option<&str>) -> Result<Tag, String>;
    async fn list_tags_for_recipe(&self, recipe_id: i64) -> Result<Vec<Tag>, String>;
    async fn add_tag_to_recipe(&self, recipe_id: i64, name: &str) -> Result<Tag, String>;
    async fn remove_tag_from_recipe(&self, recipe_id: i64, tag_id: i64) -> Result<(), String>;
}
