//! Tauri command surface. Thin — all real logic lives one layer down,
//! behind `Backend` (see `backend::mod`): either `db::*` (local SQLite)
//! or a remote HTTP call, depending on the active mode. Commands
//! themselves don't know or care which.

use crate::backend::ActiveBackend;
use crate::db::{items, recipe_items, recipes, shopping_list_items, shopping_lists, skus, tags};
use crate::woolworths::Sku;
use crate::woolworths_cart;
use serde::Deserialize;
use tauri::{Manager, State};

#[tauri::command]
pub async fn create_item(backend: State<'_, ActiveBackend>, name: String) -> Result<items::Item, String> {
    let backend = backend.lock().map_err(|e| e.to_string())?.clone();
    backend.create_item(&name).await
}

#[tauri::command]
pub async fn list_items(backend: State<'_, ActiveBackend>) -> Result<Vec<items::Item>, String> {
    let backend = backend.lock().map_err(|e| e.to_string())?.clone();
    backend.list_items().await
}

#[tauri::command]
pub async fn save_sku_to_item(
    backend: State<'_, ActiveBackend>,
    item_id: i64,
    sku: Sku,
) -> Result<skus::StoredSku, String> {
    let backend = backend.lock().map_err(|e| e.to_string())?.clone();
    backend.save_sku_to_item(item_id, &sku).await
}

#[tauri::command]
pub async fn list_skus_for_item(
    backend: State<'_, ActiveBackend>,
    item_id: i64,
) -> Result<Vec<skus::StoredSku>, String> {
    let backend = backend.lock().map_err(|e| e.to_string())?.clone();
    backend.list_skus_for_item(item_id).await
}

#[tauri::command]
pub async fn update_item_name(
    backend: State<'_, ActiveBackend>,
    item_id: i64,
    name: String,
) -> Result<items::Item, String> {
    let backend = backend.lock().map_err(|e| e.to_string())?.clone();
    backend.update_item_name(item_id, &name).await
}

#[tauri::command]
pub async fn set_item_perishable(
    backend: State<'_, ActiveBackend>,
    item_id: i64,
    is_perishable: bool,
) -> Result<items::Item, String> {
    let backend = backend.lock().map_err(|e| e.to_string())?.clone();
    backend.set_item_perishable(item_id, is_perishable).await
}

#[tauri::command]
pub async fn set_item_image_url(
    backend: State<'_, ActiveBackend>,
    item_id: i64,
    image_url: Option<String>,
) -> Result<items::Item, String> {
    let backend = backend.lock().map_err(|e| e.to_string())?.clone();
    backend.set_item_image_url(item_id, image_url.as_deref()).await
}

#[tauri::command]
pub async fn set_item_cheapest_by(
    backend: State<'_, ActiveBackend>,
    item_id: i64,
    cheapest_by: String,
) -> Result<items::Item, String> {
    let backend = backend.lock().map_err(|e| e.to_string())?.clone();
    backend.set_item_cheapest_by(item_id, &cheapest_by).await
}

#[tauri::command]
pub async fn delete_item(backend: State<'_, ActiveBackend>, item_id: i64) -> Result<(), String> {
    let backend = backend.lock().map_err(|e| e.to_string())?.clone();
    let recipes = backend.list_recipes_for_item(item_id).await?;
    if !recipes.is_empty() {
        return Err(format!(
            "Can't delete — used in: {}. Remove it from those recipes first.",
            recipes.join(", ")
        ));
    }
    backend.delete_item(item_id).await
}

#[tauri::command]
pub async fn delete_sku(backend: State<'_, ActiveBackend>, sku_id: i64) -> Result<(), String> {
    let backend = backend.lock().map_err(|e| e.to_string())?.clone();
    backend.delete_sku(sku_id).await
}

#[tauri::command]
pub async fn set_sku_preferred(
    backend: State<'_, ActiveBackend>,
    sku_id: i64,
    is_preferred: bool,
) -> Result<skus::StoredSku, String> {
    let backend = backend.lock().map_err(|e| e.to_string())?.clone();
    backend.set_sku_preferred(sku_id, is_preferred).await
}

/// Re-fetches one already-linked SKU from Woolworths and overwrites its
/// cached row — the only way today to catch a price/special/stock
/// change after a SKU was first added. Nothing does this automatically
/// yet. The Woolworths fetch itself always runs on this device (a public,
/// unauthenticated lookup) — only the save half goes through `Backend`.
#[tauri::command]
pub async fn refresh_sku(backend: State<'_, ActiveBackend>, sku_id: i64) -> Result<skus::StoredSku, String> {
    let backend = backend.lock().map_err(|e| e.to_string())?.clone();
    let stored = backend.get_sku(sku_id).await?;
    let fresh = crate::woolworths::fetch_woolworths_sku(stored.sku.sku.clone()).await?;
    backend.save_sku_to_item(stored.item_id, &fresh).await
}

/// Same as `refresh_sku`, but every SKU linked to an item — one
/// Woolworths request per SKU, done sequentially so a single failure is
/// reported without losing progress on the ones already refreshed.
#[tauri::command]
pub async fn refresh_skus_for_item(
    backend: State<'_, ActiveBackend>,
    item_id: i64,
) -> Result<Vec<skus::StoredSku>, String> {
    let backend = backend.lock().map_err(|e| e.to_string())?.clone();
    let stored_list = backend.list_skus_for_item(item_id).await?;
    let mut refreshed = Vec::with_capacity(stored_list.len());
    for stored in stored_list {
        let fresh = crate::woolworths::fetch_woolworths_sku(stored.sku.sku.clone()).await?;
        refreshed.push(backend.save_sku_to_item(item_id, &fresh).await?);
    }
    Ok(refreshed)
}

#[tauri::command]
pub async fn list_tags(backend: State<'_, ActiveBackend>) -> Result<Vec<tags::Tag>, String> {
    let backend = backend.lock().map_err(|e| e.to_string())?.clone();
    backend.list_tags().await
}

#[tauri::command]
pub async fn list_tags_for_item(
    backend: State<'_, ActiveBackend>,
    item_id: i64,
) -> Result<Vec<tags::Tag>, String> {
    let backend = backend.lock().map_err(|e| e.to_string())?.clone();
    backend.list_tags_for_item(item_id).await
}

#[tauri::command]
pub async fn add_tag_to_item(
    backend: State<'_, ActiveBackend>,
    item_id: i64,
    name: String,
) -> Result<tags::Tag, String> {
    let backend = backend.lock().map_err(|e| e.to_string())?.clone();
    backend.add_tag_to_item(item_id, &name).await
}

#[tauri::command]
pub async fn remove_tag_from_item(
    backend: State<'_, ActiveBackend>,
    item_id: i64,
    tag_id: i64,
) -> Result<(), String> {
    let backend = backend.lock().map_err(|e| e.to_string())?.clone();
    backend.remove_tag_from_item(item_id, tag_id).await
}

/// Shared by Pantry and Recipe Book — the Tags sidebar's "swap emoji"
/// affordance. `emoji: None` clears the override back to the
/// auto-picked one.
#[tauri::command]
pub async fn set_tag_emoji(
    backend: State<'_, ActiveBackend>,
    tag_id: i64,
    emoji: Option<String>,
) -> Result<tags::Tag, String> {
    let backend = backend.lock().map_err(|e| e.to_string())?.clone();
    backend.set_tag_emoji(tag_id, emoji.as_deref()).await
}

#[tauri::command]
pub async fn create_recipe(backend: State<'_, ActiveBackend>, name: String) -> Result<recipes::Recipe, String> {
    let backend = backend.lock().map_err(|e| e.to_string())?.clone();
    backend.create_recipe(&name).await
}

#[tauri::command]
pub async fn list_recipes(backend: State<'_, ActiveBackend>) -> Result<Vec<recipes::Recipe>, String> {
    let backend = backend.lock().map_err(|e| e.to_string())?.clone();
    backend.list_recipes().await
}

#[tauri::command]
pub async fn update_recipe_name(
    backend: State<'_, ActiveBackend>,
    recipe_id: i64,
    name: String,
) -> Result<recipes::Recipe, String> {
    let backend = backend.lock().map_err(|e| e.to_string())?.clone();
    backend.update_recipe_name(recipe_id, &name).await
}

#[tauri::command]
pub async fn set_recipe_image_url(
    backend: State<'_, ActiveBackend>,
    recipe_id: i64,
    image_url: Option<String>,
) -> Result<recipes::Recipe, String> {
    let backend = backend.lock().map_err(|e| e.to_string())?.clone();
    backend.set_recipe_image_url(recipe_id, image_url.as_deref()).await
}

#[tauri::command]
pub async fn delete_recipe(backend: State<'_, ActiveBackend>, recipe_id: i64) -> Result<(), String> {
    let backend = backend.lock().map_err(|e| e.to_string())?.clone();
    backend.delete_recipe(recipe_id).await
}

#[tauri::command]
pub async fn add_item_to_recipe(
    backend: State<'_, ActiveBackend>,
    recipe_id: i64,
    item_id: i64,
) -> Result<(), String> {
    let backend = backend.lock().map_err(|e| e.to_string())?.clone();
    backend.add_item_to_recipe(recipe_id, item_id).await
}

#[tauri::command]
pub async fn remove_item_from_recipe(
    backend: State<'_, ActiveBackend>,
    recipe_id: i64,
    item_id: i64,
) -> Result<(), String> {
    let backend = backend.lock().map_err(|e| e.to_string())?.clone();
    backend.remove_item_from_recipe(recipe_id, item_id).await
}

#[tauri::command]
pub async fn list_recipe_ingredients(
    backend: State<'_, ActiveBackend>,
    recipe_id: i64,
) -> Result<Vec<recipe_items::RecipeIngredient>, String> {
    let backend = backend.lock().map_err(|e| e.to_string())?.clone();
    backend.list_recipe_ingredients(recipe_id).await
}

#[tauri::command]
pub async fn set_recipe_item_quantity(
    backend: State<'_, ActiveBackend>,
    recipe_id: i64,
    item_id: i64,
    amount: Option<f64>,
    unit: Option<String>,
) -> Result<recipe_items::RecipeIngredient, String> {
    let backend = backend.lock().map_err(|e| e.to_string())?.clone();
    backend
        .set_recipe_item_quantity(recipe_id, item_id, amount, unit.as_deref())
        .await
}

#[tauri::command]
pub async fn update_recipe_method(
    backend: State<'_, ActiveBackend>,
    recipe_id: i64,
    method: String,
) -> Result<recipes::Recipe, String> {
    let backend = backend.lock().map_err(|e| e.to_string())?.clone();
    backend.update_recipe_method(recipe_id, &method).await
}

#[tauri::command]
pub async fn update_recipe_servings(
    backend: State<'_, ActiveBackend>,
    recipe_id: i64,
    servings: Option<i64>,
) -> Result<recipes::Recipe, String> {
    let backend = backend.lock().map_err(|e| e.to_string())?.clone();
    backend.update_recipe_servings(recipe_id, servings).await
}

#[tauri::command]
pub async fn update_recipe_source_url(
    backend: State<'_, ActiveBackend>,
    recipe_id: i64,
    source_url: String,
) -> Result<recipes::Recipe, String> {
    let backend = backend.lock().map_err(|e| e.to_string())?.clone();
    backend.update_recipe_source_url(recipe_id, &source_url).await
}

#[tauri::command]
pub async fn list_tags_for_recipe(
    backend: State<'_, ActiveBackend>,
    recipe_id: i64,
) -> Result<Vec<tags::Tag>, String> {
    let backend = backend.lock().map_err(|e| e.to_string())?.clone();
    backend.list_tags_for_recipe(recipe_id).await
}

#[tauri::command]
pub async fn add_tag_to_recipe(
    backend: State<'_, ActiveBackend>,
    recipe_id: i64,
    name: String,
) -> Result<tags::Tag, String> {
    let backend = backend.lock().map_err(|e| e.to_string())?.clone();
    backend.add_tag_to_recipe(recipe_id, &name).await
}

#[tauri::command]
pub async fn remove_tag_from_recipe(
    backend: State<'_, ActiveBackend>,
    recipe_id: i64,
    tag_id: i64,
) -> Result<(), String> {
    let backend = backend.lock().map_err(|e| e.to_string())?.clone();
    backend.remove_tag_from_recipe(recipe_id, tag_id).await
}

#[tauri::command]
pub async fn create_shopping_list(
    backend: State<'_, ActiveBackend>,
    name: String,
) -> Result<shopping_lists::ShoppingList, String> {
    let backend = backend.lock().map_err(|e| e.to_string())?.clone();
    backend.create_shopping_list(&name).await
}

#[tauri::command]
pub async fn list_shopping_lists(
    backend: State<'_, ActiveBackend>,
) -> Result<Vec<shopping_lists::ShoppingList>, String> {
    let backend = backend.lock().map_err(|e| e.to_string())?.clone();
    backend.list_shopping_lists().await
}

#[tauri::command]
pub async fn update_shopping_list_name(
    backend: State<'_, ActiveBackend>,
    list_id: i64,
    name: String,
) -> Result<shopping_lists::ShoppingList, String> {
    let backend = backend.lock().map_err(|e| e.to_string())?.clone();
    backend.update_shopping_list_name(list_id, &name).await
}

#[tauri::command]
pub async fn delete_shopping_list(backend: State<'_, ActiveBackend>, list_id: i64) -> Result<(), String> {
    let backend = backend.lock().map_err(|e| e.to_string())?.clone();
    backend.delete_shopping_list(list_id).await
}

#[tauri::command]
pub async fn list_shopping_list_items(
    backend: State<'_, ActiveBackend>,
    list_id: i64,
) -> Result<Vec<shopping_list_items::ShoppingListLine>, String> {
    let backend = backend.lock().map_err(|e| e.to_string())?.clone();
    backend.list_shopping_list_items(list_id).await
}

/// What's missing from the given list(s) — surfaced by `CartAdd.svelte`
/// as a review pop-up before the actual send, so a recipe ingredient
/// skipped at add-time (nominal unit, non-perishable, ...) or a regular
/// you've just run out of gets one last chance to be added.
#[tauri::command]
pub async fn list_omitted_shopping_list_items(
    backend: State<'_, ActiveBackend>,
    list_ids: Vec<i64>,
) -> Result<shopping_list_items::OmissionReport, String> {
    let backend = backend.lock().map_err(|e| e.to_string())?.clone();
    backend.list_omitted_shopping_list_items(&list_ids).await
}

#[tauri::command]
pub async fn add_item_to_shopping_list(
    backend: State<'_, ActiveBackend>,
    list_id: i64,
    item_id: i64,
    amount: Option<f64>,
    unit: Option<String>,
) -> Result<shopping_list_items::ShoppingListLine, String> {
    let backend = backend.lock().map_err(|e| e.to_string())?.clone();
    backend
        .add_item_to_shopping_list(list_id, item_id, amount, unit.as_deref())
        .await
}

#[tauri::command]
pub async fn add_recipe_to_shopping_list(
    backend: State<'_, ActiveBackend>,
    list_id: i64,
    recipe_id: i64,
    target_servings: Option<i64>,
) -> Result<Vec<shopping_list_items::ShoppingListLine>, String> {
    let backend = backend.lock().map_err(|e| e.to_string())?.clone();
    backend
        .add_recipe_to_shopping_list(list_id, recipe_id, target_servings)
        .await
}

#[tauri::command]
pub async fn set_shopping_list_recipe_quantity(
    backend: State<'_, ActiveBackend>,
    list_id: i64,
    recipe_id: i64,
    quantity: f64,
) -> Result<Vec<shopping_list_items::ShoppingListLine>, String> {
    let backend = backend.lock().map_err(|e| e.to_string())?.clone();
    backend
        .set_shopping_list_recipe_quantity(list_id, recipe_id, quantity)
        .await
}

#[tauri::command]
pub async fn set_shopping_list_item_amount(
    backend: State<'_, ActiveBackend>,
    line_id: i64,
    amount: Option<f64>,
    unit: Option<String>,
) -> Result<shopping_list_items::ShoppingListLine, String> {
    let backend = backend.lock().map_err(|e| e.to_string())?.clone();
    backend
        .set_shopping_list_item_amount(line_id, amount, unit.as_deref())
        .await
}

#[tauri::command]
pub async fn set_shopping_list_item_sku(
    backend: State<'_, ActiveBackend>,
    line_id: i64,
    sku_id: Option<i64>,
) -> Result<shopping_list_items::ShoppingListLine, String> {
    let backend = backend.lock().map_err(|e| e.to_string())?.clone();
    backend.set_shopping_list_item_sku(line_id, sku_id).await
}

#[tauri::command]
pub async fn remove_shopping_list_item(backend: State<'_, ActiveBackend>, line_id: i64) -> Result<(), String> {
    let backend = backend.lock().map_err(|e| e.to_string())?.clone();
    backend.remove_shopping_list_item(line_id).await
}

/// Empties a list's lines without deleting the list itself — the
/// "Clear list" button.
#[tauri::command]
pub async fn clear_shopping_list(backend: State<'_, ActiveBackend>, list_id: i64) -> Result<(), String> {
    let backend = backend.lock().map_err(|e| e.to_string())?.clone();
    backend.clear_shopping_list(list_id).await
}

fn round_to_increment(value: f64, increment: Option<f64>, min: Option<f64>) -> f64 {
    let step = increment.filter(|i| *i > 0.0).unwrap_or(1.0);
    let mut rounded = (value / step).ceil() * step;
    if let Some(min) = min {
        if rounded < min {
            rounded = min;
        }
    }
    (rounded * 1e6).round() / 1e6
}

struct PackSize {
    grams: Option<f64>,
    ml: Option<f64>,
}

/// Parses Woolworths' own pack-size labels ("700g", "1.5kg", "2L") — the
/// same narrow single-source format handled on the frontend
/// (+page.svelte's parsePackSize). Multi-packs/ranges/"min order …" are
/// deliberately left unparsed.
fn parse_pack_size(volume_size: Option<&str>) -> Option<PackSize> {
    let s = volume_size?.trim();
    let idx = s.find(|c: char| !c.is_ascii_digit() && c != '.')?;
    let (num_part, unit_part) = s.split_at(idx);
    let value: f64 = num_part.parse().ok()?;
    match unit_part.trim().to_lowercase().as_str() {
        "kg" => Some(PackSize { grams: Some(value * 1000.0), ml: None }),
        "g" => Some(PackSize { grams: Some(value), ml: None }),
        "l" => Some(PackSize { grams: None, ml: Some(value * 1000.0) }),
        "ml" => Some(PackSize { grams: None, ml: Some(value) }),
        _ => None,
    }
}

/// A shopping-list line's need, converted into the SKU's own native
/// purchase dimension but **not yet rounded**. Kept unrounded so that
/// two lines resolving to the same SKU (e.g. one recipe wanting "21
/// onions", another wanting "500g onions") get summed *before*
/// rounding, not after — rounding each separately then summing can
/// overcount badly (five lines each needing 100g against a 500g pack
/// would round to 5 packs individually, vs. the correct 1 pack for the
/// real 500g total).
///
/// Only two variants, not three: a literal count against an `Each` SKU
/// ("3 loaves") and a weight/volume need converted into pack-equivalents
/// against that same SKU ("1500g" of a 750g loaf = 2.0) are actually the
/// *same* unit — whole packs — just arrived at differently, so they need
/// to be summable, not kept apart. Keeping them as separate variants was
/// a real bug: two lines for the same `Each` SKU, one by count and one
/// by weight, would silently drop one instead of combining.
#[derive(Clone, Copy)]
enum RawCartNeed {
    Kg(f64),
    /// Pack-equivalents of an `Each`-sold SKU — a literal count IS
    /// already in this unit (1 loaf = 1 pack-equivalent); a weight/volume
    /// need is converted into it via the SKU's own parsed pack size.
    EachPacks(f64),
}

impl RawCartNeed {
    fn add(self, other: Self) -> Self {
        match (self, other) {
            (Self::Kg(a), Self::Kg(b)) => Self::Kg(a + b),
            (Self::EachPacks(a), Self::EachPacks(b)) => Self::EachPacks(a + b),
            // Same SKU should always resolve to the same dimension (Kg
            // vs Each is fixed by the SKU's own `unit` field) — a
            // mismatch here would mean something upstream is wrong, so
            // just keep the first rather than silently combining unlike
            // dimensions.
            (a, _) => a,
        }
    }

    fn finalize(self, sku: &Sku) -> (f64, &'static str) {
        let q = &sku.quantity;
        match self {
            Self::Kg(total) => (round_to_increment(total, q.increment, q.min), "Kg"),
            Self::EachPacks(total) => (round_to_increment(total, q.increment, q.min).max(1.0), "Each"),
        }
    }
}

/// Resolves a shopping-list line's needed amount into the SKU's own
/// native purchase dimension — a raw (unrounded) `Kg`/`EachPacks` amount
/// matching the chosen SKU's own purchase mode. Mirrors the frontend's
/// buyQuantity() primary-figure logic (+page.svelte) — duplicated rather
/// than shared since cart-add needs to resolve this standalone, not
/// depend on frontend-cached state.
fn raw_cart_need(amount: f64, unit: &str, sku: &Sku) -> Option<RawCartNeed> {
    let q = &sku.quantity;
    let grams = (unit == "g").then_some(amount);
    let ml = (unit == "mL").then_some(amount);
    let count = (unit == "count").then_some(amount);

    if q.unit.eq_ignore_ascii_case("kg") {
        if let Some(g) = grams {
            return Some(RawCartNeed::Kg(g / 1000.0));
        }
        if let (Some(c), Some(avg)) = (count, q.average_weight_per_unit) {
            return Some(RawCartNeed::Kg(c * avg));
        }
    }
    if q.unit.eq_ignore_ascii_case("each") {
        if let Some(c) = count {
            return Some(RawCartNeed::EachPacks(c));
        }
        if let Some(pack) = parse_pack_size(sku.size.volume_size.as_deref()) {
            if let (Some(g), Some(pg)) = (grams, pack.grams) {
                return Some(RawCartNeed::EachPacks(g / pg));
            }
            if let (Some(m), Some(pm)) = (ml, pack.ml) {
                return Some(RawCartNeed::EachPacks(m / pm));
            }
        }
    }
    None
}

/// Opens (or focuses, if already open) a real Woolworths page in its own
/// app window so the user can log in normally — their password goes
/// straight into Woolworths' own page, never touched by this code. The
/// resulting session cookies live in this app's own WebView2 profile,
/// which `add_shopping_lists_to_cart` reads back afterward via
/// `cookies_for_url` — no external browser file involved at all.
///
/// Points straight at the sign-in redirect rather than the homepage.
/// Woolworths' own "Sign In" button doesn't link anywhere directly — it
/// calls `GET /api/v1/bff/initiate-oidc-signin?op=login&redirectUrl=…`,
/// which mints a fresh Auth0 `state` server-side and 302s straight to
/// the login form (confirmed live: following it lands on
/// `auth.woolworths.co.nz/u/login/identifier`, same place the button
/// goes). That `state` can't be pre-built or reused, so this always
/// re-requests it rather than hardcoding an Auth0 URL. `redirectUrl`
/// just needs to be a valid Woolworths page for post-login to land
/// on — the homepage, same as before this change.
///
/// Always local-device-only, regardless of local/remote data mode — this
/// opens a native window and reads this device's own WebView2 cookie
/// jar, nothing about it goes through `Backend`.
#[tauri::command]
pub async fn open_woolworths_login(app: tauri::AppHandle) -> Result<(), String> {
    if let Some(win) = app.get_webview_window("woolworths-login") {
        win.set_focus().map_err(|e| e.to_string())?;
        return Ok(());
    }
    tauri::WebviewWindowBuilder::new(
        &app,
        "woolworths-login",
        tauri::WebviewUrl::External(
            "https://www.woolworths.co.nz/api/v1/bff/initiate-oidc-signin?op=login&redirectUrl=https%3A%2F%2Fwww.woolworths.co.nz%2F"
                .parse()
                .map_err(|e| format!("{e}"))?,
        ),
    )
    .title("Log in to Woolworths")
    .build()
    .map_err(|e| e.to_string())?;
    Ok(())
}

/// Reads the app's own WebView2 cookie store and asks Woolworths whether
/// that session can actually reach the trolley — see
/// `woolworths_cart::check_logged_in` for why this is a real request
/// rather than a cookie-name check. Always local-device-only, same
/// reasoning as `open_woolworths_login`.
#[tauri::command]
pub async fn woolworths_login_status(window: tauri::WebviewWindow) -> Result<bool, String> {
    let jar = cookie_jar_from_window(&window)?;
    woolworths_cart::check_logged_in(&jar).await
}

/// Reports what Kai can actually see and what Woolworths actually says
/// back — see `woolworths_cart::session_debug`. Exists for the case
/// where the login window is plainly signed in but Kai still says it
/// isn't, which "Not signed in" alone gives you no way to diagnose.
#[tauri::command]
pub async fn woolworths_session_debug(window: tauri::WebviewWindow) -> Result<String, String> {
    let jar = cookie_jar_from_window(&window)?;
    Ok(woolworths_cart::session_debug(&jar).await)
}

/// The flat delivery fee added at Woolworths checkout — a user-entered
/// constant (see db::settings), not fetched from anywhere. Read by
/// Settings.svelte to show/edit it, and by the Shopping Lists tab to show
/// a combined total's cost with delivery included.
#[tauri::command]
pub async fn get_delivery_fee(backend: State<'_, ActiveBackend>) -> Result<f64, String> {
    let backend = backend.lock().map_err(|e| e.to_string())?.clone();
    backend.get_delivery_fee().await
}

#[tauri::command]
pub async fn set_delivery_fee(backend: State<'_, ActiveBackend>, fee: f64) -> Result<f64, String> {
    let backend = backend.lock().map_err(|e| e.to_string())?.clone();
    backend.set_delivery_fee(fee).await
}

/// The local/remote switch — see `backend::mod`'s `LocalConn`/`resolve`
/// doc comments and CLAUDE.md's Phase B notes. Deliberately bypasses
/// `ActiveBackend` for reading/writing the setting itself (always the
/// local connection, regardless of which backend is currently active),
/// then calls `backend::resolve` to rebuild `ActiveBackend` from the
/// freshly-saved config in the same command — no restart needed, and no
/// way for the two to drift since `resolve` is the only thing that ever
/// constructs the active backend.
#[tauri::command]
pub async fn get_backend_config(
    local_conn: State<'_, crate::backend::LocalConn>,
) -> Result<crate::db::settings::BackendConfig, String> {
    let conn = local_conn.lock().map_err(|e| e.to_string())?;
    crate::db::settings::get_backend_config(&conn)
}

/// Swaps `ActiveBackend` only if `resolve` actually succeeds — picking
/// "Remote" before a URL's ever been saved is a real, expected step of
/// the flow (Settings' fields only unlock once mode is remote), not a
/// user error, so it shouldn't fail the whole mode-switch. When this
/// can't resolve yet, the previously active backend just keeps serving
/// until a later `set_remote_config` call (with an actual URL) succeeds.
fn try_rebuild_active_backend(local_conn: &crate::backend::LocalConn, active: &ActiveBackend) {
    if let Ok(rebuilt) = crate::backend::resolve(local_conn) {
        if let Ok(mut guard) = active.lock() {
            *guard = rebuilt;
        }
    }
}

#[tauri::command]
pub async fn set_backend_mode(
    mode: String,
    local_conn: State<'_, crate::backend::LocalConn>,
    active: State<'_, ActiveBackend>,
) -> Result<crate::db::settings::BackendConfig, String> {
    {
        let conn = local_conn.lock().map_err(|e| e.to_string())?;
        crate::db::settings::set_backend_mode(&conn, &mode)?;
    }
    try_rebuild_active_backend(&local_conn, &active);
    let conn = local_conn.lock().map_err(|e| e.to_string())?;
    crate::db::settings::get_backend_config(&conn)
}

#[tauri::command]
pub async fn set_remote_config(
    url: String,
    token: String,
    local_conn: State<'_, crate::backend::LocalConn>,
    active: State<'_, ActiveBackend>,
) -> Result<crate::db::settings::BackendConfig, String> {
    {
        let conn = local_conn.lock().map_err(|e| e.to_string())?;
        crate::db::settings::set_remote_config(&conn, &url, &token)?;
    }
    try_rebuild_active_backend(&local_conn, &active);
    let conn = local_conn.lock().map_err(|e| e.to_string())?;
    crate::db::settings::get_backend_config(&conn)
}

/// What Settings.svelte's "Test connection" button calls — hits the
/// server's `/status` directly with whatever URL/token are currently
/// *typed*, not necessarily the saved ones, so a user can check before
/// committing. Proves reachability and the token in one round trip.
#[tauri::command]
pub async fn test_remote_connection(url: String, token: String) -> Result<String, String> {
    let url = url.trim_end_matches('/');
    let client = reqwest::Client::new();
    let resp = client
        .get(format!("{url}/status"))
        .bearer_auth(&token)
        .send()
        .await
        .map_err(|e| format!("Couldn't reach {url}: {e}"))?;
    if resp.status().is_success() {
        Ok("Connected".to_string())
    } else if resp.status() == reqwest::StatusCode::UNAUTHORIZED {
        Err("Reached the server, but it rejected the token".to_string())
    } else {
        Err(format!("Server responded with {}", resp.status()))
    }
}

/// Opens (or focuses) the real Woolworths cart page in its own app
/// window. Shares the app's WebView2 profile with the login window, so
/// it opens already signed in. Always local-device-only.
#[tauri::command]
pub async fn open_woolworths_cart(app: tauri::AppHandle) -> Result<(), String> {
    if let Some(win) = app.get_webview_window("woolworths-cart") {
        win.set_focus().map_err(|e| e.to_string())?;
        // Re-navigating matters: the window may still be showing the
        // cart from before this add, which would look like nothing
        // happened.
        win.eval(&format!("window.location.replace('{}')", woolworths_cart::CART_PAGE_URL))
            .map_err(|e| e.to_string())?;
        return Ok(());
    }
    tauri::WebviewWindowBuilder::new(
        &app,
        "woolworths-cart",
        tauri::WebviewUrl::External(
            woolworths_cart::CART_PAGE_URL.parse().map_err(|e| format!("{e}"))?,
        ),
    )
    .title("Woolworths cart")
    .inner_size(1100.0, 800.0)
    .build()
    .map_err(|e| e.to_string())?;
    Ok(())
}

/// Shared by every command that needs the Woolworths session — the
/// cookies live in the app's own WebView2 profile, which every window
/// (main, login, cart) shares, so reading them from whichever window
/// invoked the command is equivalent to reading them from the login
/// window itself.
fn cookie_jar_from_window(
    window: &tauri::WebviewWindow,
) -> Result<woolworths_cart::CookieJar, String> {
    let raw_cookies = window
        .cookies_for_url("https://www.woolworths.co.nz/".parse().map_err(|e| format!("{e}"))?)
        .map_err(|e| format!("Couldn't read cookies from the app's Woolworths session: {e}"))?;
    let cookies: Vec<(String, String)> = raw_cookies
        .into_iter()
        .map(|c| (c.name().to_string(), c.value().to_string()))
        .collect();
    Ok(woolworths_cart::CookieJar::from_cookies(cookies))
}

/// An omission-check "+ Add" pick (see `list_omitted_shopping_list_items`)
/// that the user wants included in *this* cart-add — deliberately not
/// written to `shopping_list_items` at all. The list is the list; a
/// once-off "actually I do need rice this time" shouldn't leave it
/// sitting there forever, quietly suppressing the same reminder on
/// every future checkout (confirmed live: that's exactly what writing
/// it to the list did — added rice from one checkout's omission
/// pop-up meant it looked "on the list" from then on, so it never got
/// flagged as missing again). Resolved fresh into a SKU need and merged
/// into the same send as the real list lines, then forgotten.
#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ExtraCartItem {
    pub item_id: i64,
    pub amount: f64,
    pub unit: String,
}

/// Adds every resolvable line across one or more shopping lists — plus
/// any one-off `extra_items` picked from the omission-check pop-up — to
/// the user's real Woolworths cart, using the session cookies from the
/// app's own login window (see `open_woolworths_login`). Lines with no
/// chosen SKU or an amount/unit combo we can't resolve to a buy quantity
/// are reported back as failed rather than skipped silently.
///
/// Merging happens across *all* the given lists (and any extra items) at
/// once, not per list — see the grouping comment below for why that
/// matters. Two lists that both want onions have to become one combined
/// cart quantity, exactly like two lines within a single list do.
///
/// Mixed local/remote case: the shopping-list/SKU *reads* below go
/// through `Backend` (work in either mode — a remote user's cart-add
/// still needs the shared list data), but the cookie read and the actual
/// Woolworths POST (`woolworths_cart::add_all`) are always this device's
/// own session, never routed through `Backend` — that's not shared data,
/// it's this device's own login.
#[tauri::command]
pub async fn add_shopping_lists_to_cart(
    backend: State<'_, ActiveBackend>,
    window: tauri::WebviewWindow,
    list_ids: Vec<i64>,
    extra_items: Vec<ExtraCartItem>,
) -> Result<woolworths_cart::CartAddSummary, String> {
    if list_ids.is_empty() {
        return Err("No shopping lists selected".into());
    }

    fn merge_need(
        merged: &mut std::collections::HashMap<String, (RawCartNeed, Sku, Vec<String>)>,
        sku: Sku,
        name: String,
        need: RawCartNeed,
    ) {
        merged
            .entry(sku.sku.clone())
            .and_modify(|(existing, _, names)| {
                *existing = existing.add(need);
                // Same item merging across lines/lists is the common
                // case (e.g. two lists both wanting onions) — don't
                // repeat its name for every line that contributed. A
                // genuinely different item resolving to the same SKU
                // still gets listed, since that's actually worth
                // showing.
                if !names.contains(&name) {
                    names.push(name.clone());
                }
            })
            .or_insert_with(|| (need, sku, vec![name]));
    }

    let backend = backend.lock().map_err(|e| e.to_string())?.clone();

    let mut lines = Vec::new();
    for list_id in &list_ids {
        lines.extend(backend.list_shopping_list_items(*list_id).await?);
    }

    // Grouped by SKU code, not by shopping-list line: two lines can
    // resolve to the same real-world product (e.g. one recipe wants
    // "21 onions", another wants "500g onions", both against the
    // same loose-onions SKU) and Woolworths' cart-add appears to
    // *set* quantity per SKU rather than add to it — sending two
    // separate calls for the same SKU silently overwrites the first
    // with the second instead of combining them. Merging here, once,
    // before any request goes out, is what actually fixes that. The
    // same reasoning is why several lists merge together rather than
    // being sent one list at a time.
    let mut merged: std::collections::HashMap<String, (RawCartNeed, Sku, Vec<String>)> =
        std::collections::HashMap::new();
    let mut skipped = Vec::new();
    for line in lines {
        let (Some(amount), Some(unit), Some(sku_summary)) =
            (line.amount, line.unit.clone(), line.sku.clone())
        else {
            skipped.push(line.item_name.clone());
            continue;
        };
        let Ok(stored) = backend.get_sku(sku_summary.id).await else {
            skipped.push(line.item_name.clone());
            continue;
        };
        match raw_cart_need(amount, &unit, &stored.sku) {
            Some(need) => merge_need(&mut merged, stored.sku.clone(), line.item_name.clone(), need),
            None => skipped.push(line.item_name.clone()),
        }
    }

    // Extra picks from the omission-check pop-up — resolved the same
    // way a real line would be (cheapest linked SKU, same as a fresh
    // item-drop auto-picks), merged into the same map, but never
    // written to `shopping_list_items`.
    for extra in extra_items {
        let Ok(item) = backend.get_item(extra.item_id).await else {
            continue; // unknown item id — nothing sensible to report
        };
        let sku_id = backend.cheapest_sku_id(extra.item_id).await?;
        let Some(sku_id) = sku_id else {
            skipped.push(item.name);
            continue;
        };
        let Ok(stored) = backend.get_sku(sku_id).await else {
            skipped.push(item.name);
            continue;
        };
        match raw_cart_need(extra.amount, &extra.unit, &stored.sku) {
            Some(need) => merge_need(&mut merged, stored.sku.clone(), item.name, need),
            None => skipped.push(item.name),
        }
    }

    let cart_items = merged
        .into_values()
        .map(|(need, sku, names)| {
            let (quantity, pricing_unit) = need.finalize(&sku);
            woolworths_cart::CartLineInput {
                name: names.join(" + "),
                sku: sku.sku.clone(),
                quantity,
                pricing_unit: pricing_unit.to_string(),
            }
        })
        .collect::<Vec<_>>();

    let jar = cookie_jar_from_window(&window)?;

    let mut summary = woolworths_cart::add_all(jar, cart_items).await?;
    for name in skipped.drain(..) {
        summary.results.push(woolworths_cart::CartLineResult {
            name,
            sku: String::new(),
            quantity: 0.0,
            pricing_unit: String::new(),
            ok: false,
            error: Some("Couldn't work out a buy quantity for this line — check it manually".into()),
        });
    }
    Ok(summary)
}

#[cfg(test)]
mod tests {
    use super::*;

    /// The merge that makes combining several shopping lists correct:
    /// two lists both wanting the same SKU have to sum into one cart
    /// quantity, because Woolworths' cart-add *sets* rather than adds
    /// per SKU (see `add_shopping_lists_to_cart`).
    #[test]
    fn same_sku_across_lists_sums() {
        // Two loaves on one list + one on another = three, not one.
        let merged = RawCartNeed::EachPacks(2.0).add(RawCartNeed::EachPacks(1.0));
        assert!(matches!(merged, RawCartNeed::EachPacks(n) if (n - 3.0).abs() < f64::EPSILON));

        // Weight-sold SKU: 500g here + 300g there = 0.8kg.
        let merged = RawCartNeed::Kg(0.5).add(RawCartNeed::Kg(0.3));
        assert!(matches!(merged, RawCartNeed::Kg(n) if (n - 0.8).abs() < 1e-9));
    }

    /// Rounding must happen once, after merging — rounding each list's
    /// need separately then adding would overcount badly (five 100g
    /// needs against a 500g pack should be 1 pack, not 5).
    #[test]
    fn rounds_after_merging_not_before() {
        let five_hundred_grams_total = (0..5).fold(RawCartNeed::EachPacks(0.0), |acc, _| {
            acc.add(RawCartNeed::EachPacks(0.2))
        });
        match five_hundred_grams_total {
            RawCartNeed::EachPacks(n) => {
                assert!((n - 1.0).abs() < 1e-9, "expected 1.0 pack-equivalent, got {n}");
                assert_eq!(round_to_increment(n, None, None).max(1.0), 1.0);
            }
            _ => panic!("dimension changed unexpectedly"),
        }
    }

    #[test]
    fn round_to_increment_respects_steps_and_min() {
        // Loose onions: 0.1kg steps, 0.1kg minimum.
        assert!((round_to_increment(0.34, Some(0.1), Some(0.1)) - 0.4).abs() < 1e-9);
        // Below the minimum order still lands on the minimum.
        assert!((round_to_increment(0.02, Some(0.1), Some(0.1)) - 0.1).abs() < 1e-9);
    }
}
