//! The local SQLite backend — every method is the exact same call to
//! `db::*` that `commands.rs` used to make directly, just moved one layer
//! down. Zero behavior change from before `Backend` existed; this is the
//! "local" half of Phase B, built and verified before the "remote" half
//! (a `RemoteBackend` hitting a Postgres-backed server) exists at all.

use super::items::ItemsBackend;
use super::recipe_items::RecipeItemsBackend;
use super::recipes::RecipesBackend;
use super::settings::SettingsBackend;
use super::shopping_list_items::ShoppingListItemsBackend;
use super::shopping_lists::ShoppingListsBackend;
use super::skus::SkusBackend;
use super::tags::TagsBackend;
use crate::db::{
    items, recipe_items, recipes, settings, shopping_list_items, shopping_lists, skus, tags,
};
use crate::db::items::Item;
use crate::db::recipe_items::RecipeIngredient;
use crate::db::recipes::Recipe;
use crate::db::shopping_list_items::{OmissionReport, ShoppingListLine};
use crate::db::shopping_lists::ShoppingList;
use crate::db::skus::StoredSku;
use crate::db::tags::Tag;
use crate::woolworths::Sku;
use async_trait::async_trait;
use rusqlite::Connection;
use std::sync::{Arc, Mutex, MutexGuard};

/// Wraps the same shared `LocalConn` the app always keeps open (see
/// `backend::mod`) rather than owning its own connection — so switching
/// away from local mode and back doesn't open/close the SQLite file, it
/// just stops/resumes routing through it.
pub struct LocalBackend {
    conn: Arc<Mutex<Connection>>,
}

impl LocalBackend {
    pub fn new(conn: Arc<Mutex<Connection>>) -> Self {
        Self { conn }
    }

    fn lock(&self) -> Result<MutexGuard<'_, Connection>, String> {
        self.conn.lock().map_err(|e| e.to_string())
    }
}

#[async_trait]
impl ItemsBackend for LocalBackend {
    async fn create_item(&self, name: &str) -> Result<Item, String> {
        items::create(&*self.lock()?, name)
    }
    async fn get_item(&self, id: i64) -> Result<Item, String> {
        items::get(&*self.lock()?, id)
    }
    async fn update_item_name(&self, id: i64, name: &str) -> Result<Item, String> {
        items::update_name(&*self.lock()?, id, name)
    }
    async fn set_item_perishable(&self, id: i64, is_perishable: bool) -> Result<Item, String> {
        items::set_perishable(&*self.lock()?, id, is_perishable)
    }
    async fn set_item_image_url(&self, id: i64, image_url: Option<&str>) -> Result<Item, String> {
        items::set_image_url(&*self.lock()?, id, image_url)
    }
    async fn set_item_cheapest_by(&self, id: i64, cheapest_by: &str) -> Result<Item, String> {
        items::set_cheapest_by(&*self.lock()?, id, cheapest_by)
    }
    async fn delete_item(&self, id: i64) -> Result<(), String> {
        items::delete(&*self.lock()?, id)
    }
    async fn list_items(&self) -> Result<Vec<Item>, String> {
        items::list(&*self.lock()?)
    }
}

#[async_trait]
impl SkusBackend for LocalBackend {
    async fn save_sku_to_item(&self, item_id: i64, sku: &Sku) -> Result<StoredSku, String> {
        skus::save(&*self.lock()?, item_id, sku)
    }
    async fn get_sku(&self, id: i64) -> Result<StoredSku, String> {
        skus::get(&*self.lock()?, id)
    }
    async fn list_skus_for_item(&self, item_id: i64) -> Result<Vec<StoredSku>, String> {
        skus::list_for_item(&*self.lock()?, item_id)
    }
    async fn delete_sku(&self, id: i64) -> Result<(), String> {
        skus::delete(&*self.lock()?, id)
    }
    async fn set_sku_preferred(&self, id: i64, is_preferred: bool) -> Result<StoredSku, String> {
        skus::set_preferred(&*self.lock()?, id, is_preferred)
    }
}

#[async_trait]
impl TagsBackend for LocalBackend {
    async fn list_tags(&self) -> Result<Vec<Tag>, String> {
        tags::list_all(&*self.lock()?)
    }
    async fn list_tags_for_item(&self, item_id: i64) -> Result<Vec<Tag>, String> {
        tags::list_for_item(&*self.lock()?, item_id)
    }
    async fn add_tag_to_item(&self, item_id: i64, name: &str) -> Result<Tag, String> {
        tags::add_to_item(&*self.lock()?, item_id, name)
    }
    async fn remove_tag_from_item(&self, item_id: i64, tag_id: i64) -> Result<(), String> {
        tags::remove_from_item(&*self.lock()?, item_id, tag_id)
    }
    async fn set_tag_emoji(&self, tag_id: i64, emoji: Option<&str>) -> Result<Tag, String> {
        tags::set_emoji(&*self.lock()?, tag_id, emoji)
    }
    async fn list_tags_for_recipe(&self, recipe_id: i64) -> Result<Vec<Tag>, String> {
        tags::list_for_recipe(&*self.lock()?, recipe_id)
    }
    async fn add_tag_to_recipe(&self, recipe_id: i64, name: &str) -> Result<Tag, String> {
        tags::add_to_recipe(&*self.lock()?, recipe_id, name)
    }
    async fn remove_tag_from_recipe(&self, recipe_id: i64, tag_id: i64) -> Result<(), String> {
        tags::remove_from_recipe(&*self.lock()?, recipe_id, tag_id)
    }
}

#[async_trait]
impl RecipesBackend for LocalBackend {
    async fn create_recipe(&self, name: &str) -> Result<Recipe, String> {
        recipes::create(&*self.lock()?, name)
    }
    async fn list_recipes(&self) -> Result<Vec<Recipe>, String> {
        recipes::list(&*self.lock()?)
    }
    async fn update_recipe_name(&self, id: i64, name: &str) -> Result<Recipe, String> {
        recipes::update_name(&*self.lock()?, id, name)
    }
    async fn set_recipe_image_url(&self, id: i64, image_url: Option<&str>) -> Result<Recipe, String> {
        recipes::set_image_url(&*self.lock()?, id, image_url)
    }
    async fn delete_recipe(&self, id: i64) -> Result<(), String> {
        recipes::delete(&*self.lock()?, id)
    }
    async fn update_recipe_method(&self, id: i64, method: &str) -> Result<Recipe, String> {
        recipes::update_method(&*self.lock()?, id, method)
    }
    async fn update_recipe_servings(&self, id: i64, servings: Option<i64>) -> Result<Recipe, String> {
        recipes::update_servings(&*self.lock()?, id, servings)
    }
    async fn update_recipe_source_url(&self, id: i64, source_url: &str) -> Result<Recipe, String> {
        recipes::update_source_url(&*self.lock()?, id, source_url)
    }
}

#[async_trait]
impl RecipeItemsBackend for LocalBackend {
    async fn add_item_to_recipe(&self, recipe_id: i64, item_id: i64) -> Result<(), String> {
        recipe_items::add(&*self.lock()?, recipe_id, item_id)
    }
    async fn remove_item_from_recipe(&self, recipe_id: i64, item_id: i64) -> Result<(), String> {
        recipe_items::remove(&*self.lock()?, recipe_id, item_id)
    }
    async fn list_recipe_ingredients(&self, recipe_id: i64) -> Result<Vec<RecipeIngredient>, String> {
        recipe_items::list_for_recipe(&*self.lock()?, recipe_id)
    }
    async fn set_recipe_item_quantity(
        &self,
        recipe_id: i64,
        item_id: i64,
        amount: Option<f64>,
        unit: Option<&str>,
    ) -> Result<RecipeIngredient, String> {
        recipe_items::set_quantity(&*self.lock()?, recipe_id, item_id, amount, unit)
    }
    async fn list_recipes_for_item(&self, item_id: i64) -> Result<Vec<String>, String> {
        recipe_items::list_recipes_for_item(&*self.lock()?, item_id)
    }
}

#[async_trait]
impl ShoppingListsBackend for LocalBackend {
    async fn create_shopping_list(&self, name: &str) -> Result<ShoppingList, String> {
        shopping_lists::create(&*self.lock()?, name)
    }
    async fn list_shopping_lists(&self) -> Result<Vec<ShoppingList>, String> {
        shopping_lists::list(&*self.lock()?)
    }
    async fn update_shopping_list_name(&self, id: i64, name: &str) -> Result<ShoppingList, String> {
        shopping_lists::update_name(&*self.lock()?, id, name)
    }
    async fn delete_shopping_list(&self, id: i64) -> Result<(), String> {
        shopping_lists::delete(&*self.lock()?, id)
    }
}

#[async_trait]
impl ShoppingListItemsBackend for LocalBackend {
    async fn list_shopping_list_items(&self, list_id: i64) -> Result<Vec<ShoppingListLine>, String> {
        shopping_list_items::list_for_list(&*self.lock()?, list_id)
    }
    async fn list_omitted_shopping_list_items(
        &self,
        list_ids: &[i64],
    ) -> Result<OmissionReport, String> {
        shopping_list_items::list_omitted(&*self.lock()?, list_ids)
    }
    async fn add_item_to_shopping_list(
        &self,
        list_id: i64,
        item_id: i64,
        amount: Option<f64>,
        unit: Option<&str>,
    ) -> Result<ShoppingListLine, String> {
        shopping_list_items::add_item(&*self.lock()?, list_id, item_id, amount, unit, None)
    }
    async fn add_recipe_to_shopping_list(
        &self,
        list_id: i64,
        recipe_id: i64,
        target_servings: Option<i64>,
    ) -> Result<Vec<ShoppingListLine>, String> {
        shopping_list_items::add_recipe(&*self.lock()?, list_id, recipe_id, target_servings)
    }
    async fn set_shopping_list_recipe_quantity(
        &self,
        list_id: i64,
        recipe_id: i64,
        quantity: f64,
    ) -> Result<Vec<ShoppingListLine>, String> {
        shopping_list_items::set_recipe_quantity(&*self.lock()?, list_id, recipe_id, quantity)
    }
    async fn set_shopping_list_item_amount(
        &self,
        line_id: i64,
        amount: Option<f64>,
        unit: Option<&str>,
    ) -> Result<ShoppingListLine, String> {
        shopping_list_items::set_amount(&*self.lock()?, line_id, amount, unit)
    }
    async fn set_shopping_list_item_sku(
        &self,
        line_id: i64,
        sku_id: Option<i64>,
    ) -> Result<ShoppingListLine, String> {
        shopping_list_items::set_sku(&*self.lock()?, line_id, sku_id)
    }
    async fn remove_shopping_list_item(&self, line_id: i64) -> Result<(), String> {
        shopping_list_items::remove(&*self.lock()?, line_id)
    }
    async fn clear_shopping_list(&self, list_id: i64) -> Result<(), String> {
        shopping_list_items::clear(&*self.lock()?, list_id)
    }
    async fn cheapest_sku_id(&self, item_id: i64) -> Result<Option<i64>, String> {
        shopping_list_items::cheapest_sku_id(&*self.lock()?, item_id)
    }
}

#[async_trait]
impl SettingsBackend for LocalBackend {
    async fn get_delivery_fee(&self) -> Result<f64, String> {
        settings::get_delivery_fee(&*self.lock()?)
    }
    async fn set_delivery_fee(&self, fee: f64) -> Result<f64, String> {
        settings::set_delivery_fee(&*self.lock()?, fee)
    }
}
