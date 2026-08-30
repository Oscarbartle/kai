//! The remote backend — every method is one HTTP call to a `kai-server`
//! instance (see `crates/kai-server`), using the exact routes that crate
//! exposes. Method-for-method this mirrors `LocalBackend`; the difference
//! is entirely in how each call reaches the data, not what it returns —
//! `commands.rs` doesn't know or care which one it's talking to.

use super::items::ItemsBackend;
use super::recipe_items::RecipeItemsBackend;
use super::recipes::RecipesBackend;
use super::settings::SettingsBackend;
use super::shopping_list_items::ShoppingListItemsBackend;
use super::shopping_lists::ShoppingListsBackend;
use super::skus::SkusBackend;
use super::tags::TagsBackend;
use crate::db::items::Item;
use crate::db::recipe_items::RecipeIngredient;
use crate::db::recipes::Recipe;
use crate::db::shopping_list_items::{OmissionReport, ShoppingListLine};
use crate::db::shopping_lists::ShoppingList;
use crate::db::skus::StoredSku;
use crate::db::tags::Tag;
use crate::woolworths::Sku;
use async_trait::async_trait;
use serde::de::DeserializeOwned;
use serde::{Deserialize, Serialize};
use serde_json::json;

pub struct RemoteBackend {
    client: reqwest::Client,
    base_url: String,
    token: String,
}

impl RemoteBackend {
    pub fn new(base_url: String, token: String) -> Self {
        Self {
            client: reqwest::Client::new(),
            base_url: base_url.trim_end_matches('/').to_string(),
            token,
        }
    }

    fn url(&self, path: &str) -> String {
        format!("{}{}", self.base_url, path)
    }

    async fn get<T: DeserializeOwned>(&self, path: &str) -> Result<T, String> {
        let resp = self
            .client
            .get(self.url(path))
            .bearer_auth(&self.token)
            .send()
            .await
            .map_err(|e| format!("Couldn't reach remote server: {e}"))?;
        Self::body(resp).await
    }

    async fn post<B: Serialize + ?Sized, T: DeserializeOwned>(
        &self,
        path: &str,
        body: &B,
    ) -> Result<T, String> {
        let resp = self
            .client
            .post(self.url(path))
            .bearer_auth(&self.token)
            .json(body)
            .send()
            .await
            .map_err(|e| format!("Couldn't reach remote server: {e}"))?;
        Self::body(resp).await
    }

    async fn post_unit<B: Serialize + ?Sized>(&self, path: &str, body: &B) -> Result<(), String> {
        let resp = self
            .client
            .post(self.url(path))
            .bearer_auth(&self.token)
            .json(body)
            .send()
            .await
            .map_err(|e| format!("Couldn't reach remote server: {e}"))?;
        Self::empty_body(resp).await
    }

    async fn patch<B: Serialize + ?Sized, T: DeserializeOwned>(
        &self,
        path: &str,
        body: &B,
    ) -> Result<T, String> {
        let resp = self
            .client
            .patch(self.url(path))
            .bearer_auth(&self.token)
            .json(body)
            .send()
            .await
            .map_err(|e| format!("Couldn't reach remote server: {e}"))?;
        Self::body(resp).await
    }

    async fn put<B: Serialize + ?Sized, T: DeserializeOwned>(
        &self,
        path: &str,
        body: &B,
    ) -> Result<T, String> {
        let resp = self
            .client
            .put(self.url(path))
            .bearer_auth(&self.token)
            .json(body)
            .send()
            .await
            .map_err(|e| format!("Couldn't reach remote server: {e}"))?;
        Self::body(resp).await
    }

    async fn delete(&self, path: &str) -> Result<(), String> {
        let resp = self
            .client
            .delete(self.url(path))
            .bearer_auth(&self.token)
            .send()
            .await
            .map_err(|e| format!("Couldn't reach remote server: {e}"))?;
        Self::empty_body(resp).await
    }

    async fn body<T: DeserializeOwned>(resp: reqwest::Response) -> Result<T, String> {
        let status = resp.status();
        if status.is_success() {
            resp.json::<T>()
                .await
                .map_err(|e| format!("Couldn't parse remote server response: {e}"))
        } else {
            Err(Self::error_message(resp, status).await)
        }
    }

    async fn empty_body(resp: reqwest::Response) -> Result<(), String> {
        let status = resp.status();
        if status.is_success() {
            Ok(())
        } else {
            Err(Self::error_message(resp, status).await)
        }
    }

    async fn error_message(resp: reqwest::Response, status: reqwest::StatusCode) -> String {
        #[derive(Deserialize)]
        struct ErrBody {
            error: String,
        }
        match resp.json::<ErrBody>().await {
            Ok(e) => e.error,
            Err(_) => format!("Remote server returned {status}"),
        }
    }
}

#[async_trait]
impl ItemsBackend for RemoteBackend {
    async fn create_item(&self, name: &str) -> Result<Item, String> {
        self.post("/items", &json!({ "name": name })).await
    }
    async fn get_item(&self, id: i64) -> Result<Item, String> {
        self.get(&format!("/items/{id}")).await
    }
    async fn update_item_name(&self, id: i64, name: &str) -> Result<Item, String> {
        self.patch(&format!("/items/{id}/name"), &json!({ "name": name })).await
    }
    async fn set_item_perishable(&self, id: i64, is_perishable: bool) -> Result<Item, String> {
        self.patch(&format!("/items/{id}/perishable"), &json!({ "is_perishable": is_perishable }))
            .await
    }
    async fn set_item_image_url(&self, id: i64, image_url: Option<&str>) -> Result<Item, String> {
        self.patch(&format!("/items/{id}/image-url"), &json!({ "image_url": image_url }))
            .await
    }
    async fn set_item_cheapest_by(&self, id: i64, cheapest_by: &str) -> Result<Item, String> {
        self.patch(&format!("/items/{id}/cheapest-by"), &json!({ "cheapest_by": cheapest_by }))
            .await
    }
    async fn delete_item(&self, id: i64) -> Result<(), String> {
        self.delete(&format!("/items/{id}")).await
    }
    async fn list_items(&self) -> Result<Vec<Item>, String> {
        self.get("/items").await
    }
}

#[async_trait]
impl SkusBackend for RemoteBackend {
    async fn save_sku_to_item(&self, item_id: i64, sku: &Sku) -> Result<StoredSku, String> {
        self.post(&format!("/items/{item_id}/skus"), sku).await
    }
    async fn get_sku(&self, id: i64) -> Result<StoredSku, String> {
        self.get(&format!("/skus/{id}")).await
    }
    async fn list_skus_for_item(&self, item_id: i64) -> Result<Vec<StoredSku>, String> {
        self.get(&format!("/items/{item_id}/skus")).await
    }
    async fn delete_sku(&self, id: i64) -> Result<(), String> {
        self.delete(&format!("/skus/{id}")).await
    }
    async fn set_sku_preferred(&self, id: i64, is_preferred: bool) -> Result<StoredSku, String> {
        self.patch(&format!("/skus/{id}/preferred"), &json!({ "is_preferred": is_preferred }))
            .await
    }
}

#[async_trait]
impl TagsBackend for RemoteBackend {
    async fn list_tags(&self) -> Result<Vec<Tag>, String> {
        self.get("/tags").await
    }
    async fn list_tags_for_item(&self, item_id: i64) -> Result<Vec<Tag>, String> {
        self.get(&format!("/items/{item_id}/tags")).await
    }
    async fn add_tag_to_item(&self, item_id: i64, name: &str) -> Result<Tag, String> {
        self.post(&format!("/items/{item_id}/tags"), &json!({ "name": name })).await
    }
    async fn remove_tag_from_item(&self, item_id: i64, tag_id: i64) -> Result<(), String> {
        self.delete(&format!("/items/{item_id}/tags/{tag_id}")).await
    }
    async fn set_tag_emoji(&self, tag_id: i64, emoji: Option<&str>) -> Result<Tag, String> {
        self.patch(&format!("/tags/{tag_id}/emoji"), &json!({ "emoji": emoji })).await
    }
    async fn list_tags_for_recipe(&self, recipe_id: i64) -> Result<Vec<Tag>, String> {
        self.get(&format!("/recipes/{recipe_id}/tags")).await
    }
    async fn add_tag_to_recipe(&self, recipe_id: i64, name: &str) -> Result<Tag, String> {
        self.post(&format!("/recipes/{recipe_id}/tags"), &json!({ "name": name })).await
    }
    async fn remove_tag_from_recipe(&self, recipe_id: i64, tag_id: i64) -> Result<(), String> {
        self.delete(&format!("/recipes/{recipe_id}/tags/{tag_id}")).await
    }
}

#[async_trait]
impl RecipesBackend for RemoteBackend {
    async fn create_recipe(&self, name: &str) -> Result<Recipe, String> {
        self.post("/recipes", &json!({ "name": name })).await
    }
    async fn list_recipes(&self) -> Result<Vec<Recipe>, String> {
        self.get("/recipes").await
    }
    async fn update_recipe_name(&self, id: i64, name: &str) -> Result<Recipe, String> {
        self.patch(&format!("/recipes/{id}/name"), &json!({ "name": name })).await
    }
    async fn set_recipe_image_url(&self, id: i64, image_url: Option<&str>) -> Result<Recipe, String> {
        self.patch(&format!("/recipes/{id}/image-url"), &json!({ "image_url": image_url }))
            .await
    }
    async fn delete_recipe(&self, id: i64) -> Result<(), String> {
        self.delete(&format!("/recipes/{id}")).await
    }
    async fn update_recipe_method(&self, id: i64, method: &str) -> Result<Recipe, String> {
        self.patch(&format!("/recipes/{id}/method"), &json!({ "method": method })).await
    }
    async fn update_recipe_servings(&self, id: i64, servings: Option<i64>) -> Result<Recipe, String> {
        self.patch(&format!("/recipes/{id}/servings"), &json!({ "servings": servings })).await
    }
    async fn update_recipe_source_url(&self, id: i64, source_url: &str) -> Result<Recipe, String> {
        self.patch(&format!("/recipes/{id}/source-url"), &json!({ "source_url": source_url }))
            .await
    }
}

#[async_trait]
impl RecipeItemsBackend for RemoteBackend {
    async fn add_item_to_recipe(&self, recipe_id: i64, item_id: i64) -> Result<(), String> {
        self.post_unit(&format!("/recipes/{recipe_id}/items"), &json!({ "item_id": item_id }))
            .await
    }
    async fn remove_item_from_recipe(&self, recipe_id: i64, item_id: i64) -> Result<(), String> {
        self.delete(&format!("/recipes/{recipe_id}/items/{item_id}")).await
    }
    async fn list_recipe_ingredients(&self, recipe_id: i64) -> Result<Vec<RecipeIngredient>, String> {
        self.get(&format!("/recipes/{recipe_id}/ingredients")).await
    }
    async fn set_recipe_item_quantity(
        &self,
        recipe_id: i64,
        item_id: i64,
        amount: Option<f64>,
        unit: Option<&str>,
    ) -> Result<RecipeIngredient, String> {
        self.patch(
            &format!("/recipes/{recipe_id}/items/{item_id}/quantity"),
            &json!({ "amount": amount, "unit": unit }),
        )
        .await
    }
    async fn list_recipes_for_item(&self, item_id: i64) -> Result<Vec<String>, String> {
        self.get(&format!("/items/{item_id}/recipes")).await
    }
}

#[async_trait]
impl ShoppingListsBackend for RemoteBackend {
    async fn create_shopping_list(&self, name: &str) -> Result<ShoppingList, String> {
        self.post("/shopping-lists", &json!({ "name": name })).await
    }
    async fn list_shopping_lists(&self) -> Result<Vec<ShoppingList>, String> {
        self.get("/shopping-lists").await
    }
    async fn update_shopping_list_name(&self, id: i64, name: &str) -> Result<ShoppingList, String> {
        self.patch(&format!("/shopping-lists/{id}/name"), &json!({ "name": name })).await
    }
    async fn delete_shopping_list(&self, id: i64) -> Result<(), String> {
        self.delete(&format!("/shopping-lists/{id}")).await
    }
}

#[async_trait]
impl ShoppingListItemsBackend for RemoteBackend {
    async fn list_shopping_list_items(&self, list_id: i64) -> Result<Vec<ShoppingListLine>, String> {
        self.get(&format!("/shopping-lists/{list_id}/items")).await
    }
    async fn list_omitted_shopping_list_items(
        &self,
        list_ids: &[i64],
    ) -> Result<OmissionReport, String> {
        self.post("/shopping-lists/omitted", &json!({ "list_ids": list_ids })).await
    }
    async fn add_item_to_shopping_list(
        &self,
        list_id: i64,
        item_id: i64,
        amount: Option<f64>,
        unit: Option<&str>,
    ) -> Result<ShoppingListLine, String> {
        self.post(
            &format!("/shopping-lists/{list_id}/items"),
            &json!({ "item_id": item_id, "amount": amount, "unit": unit }),
        )
        .await
    }
    async fn add_recipe_to_shopping_list(
        &self,
        list_id: i64,
        recipe_id: i64,
        target_servings: Option<i64>,
    ) -> Result<Vec<ShoppingListLine>, String> {
        self.post(
            &format!("/shopping-lists/{list_id}/recipes"),
            &json!({ "recipe_id": recipe_id, "target_servings": target_servings }),
        )
        .await
    }
    async fn set_shopping_list_recipe_quantity(
        &self,
        list_id: i64,
        recipe_id: i64,
        quantity: f64,
    ) -> Result<Vec<ShoppingListLine>, String> {
        self.patch(
            &format!("/shopping-lists/{list_id}/recipes/{recipe_id}/quantity"),
            &json!({ "quantity": quantity }),
        )
        .await
    }
    async fn set_shopping_list_item_amount(
        &self,
        line_id: i64,
        amount: Option<f64>,
        unit: Option<&str>,
    ) -> Result<ShoppingListLine, String> {
        self.patch(
            &format!("/shopping-list-items/{line_id}/amount"),
            &json!({ "amount": amount, "unit": unit }),
        )
        .await
    }
    async fn set_shopping_list_item_sku(
        &self,
        line_id: i64,
        sku_id: Option<i64>,
    ) -> Result<ShoppingListLine, String> {
        self.patch(&format!("/shopping-list-items/{line_id}/sku"), &json!({ "sku_id": sku_id }))
            .await
    }
    async fn remove_shopping_list_item(&self, line_id: i64) -> Result<(), String> {
        self.delete(&format!("/shopping-list-items/{line_id}")).await
    }
    async fn cheapest_sku_id(&self, item_id: i64) -> Result<Option<i64>, String> {
        self.get(&format!("/items/{item_id}/cheapest-sku")).await
    }
}

#[async_trait]
impl SettingsBackend for RemoteBackend {
    async fn get_delivery_fee(&self) -> Result<f64, String> {
        self.get("/delivery-fee").await
    }
    async fn set_delivery_fee(&self, fee: f64) -> Result<f64, String> {
        self.put("/delivery-fee", &json!({ "fee": fee })).await
    }
}
