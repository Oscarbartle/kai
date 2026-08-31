//! Proves `RemoteBackend`'s HTTP calls actually match what `kai-server`
//! expects — not just that both sides compile against the same
//! `kai-shared` types. Same approach `kai-server`'s own `tests/http.rs`
//! takes: a real embedded, ephemeral Postgres (no Docker needed) behind a
//! real `axum::serve` on a real socket, hit with real HTTP calls — this
//! time through `RemoteBackend` itself, the exact code path the desktop
//! app uses once Settings (Stage 5) lets a user flip to remote mode.
//!
//! Deliberately covers one path through each domain rather than every
//! method — `kai-server`'s own tests already prove its db logic in depth;
//! this one is about the wire contract between the two crates (route
//! paths, HTTP verbs, request/response JSON shapes) matching in fact, not
//! just in the plan each side was written from.

use kai_lib::backend::{
    ItemsBackend, RecipeItemsBackend, RecipesBackend, RemoteBackend, SettingsBackend,
    ShoppingListItemsBackend, ShoppingListsBackend, SkusBackend, TagsBackend,
};
use kai_shared::skus::{Sku, SkuPrice, SkuQuantity, SkuSize};
use postgresql_embedded::PostgreSQL;

fn fixture_sku() -> Sku {
    Sku {
        provider: "woolworths".to_string(),
        sku: "144329".to_string(),
        name: "Onions Brown".to_string(),
        brand: None,
        variety: Some("Brown".to_string()),
        price: SkuPrice {
            original_price: Some(4.5),
            sale_price: Some(3.5),
            is_special: true,
            save_percentage: Some(22.0),
            promotion_start_date: Some("2026-08-24T00:00:00".to_string()),
            promotion_end_date: Some("2026-08-31T00:00:00".to_string()),
        },
        size: SkuSize {
            cup_price: Some(3.5),
            cup_measure: Some("1kg".to_string()),
            package_type: None,
            volume_size: None,
        },
        quantity: SkuQuantity {
            unit: "Kg".to_string(),
            min: Some(0.1),
            max: None,
            increment: Some(0.1),
            supports_both_each_and_kg: true,
            average_weight_per_unit: Some(0.15),
        },
        availability_status: Some("In Stock".to_string()),
        stock_level: None,
        images: vec!["https://example.com/onion.jpg".to_string()],
        allergens: vec![],
        ingredients: vec![],
    }
}

#[tokio::test]
async fn remote_backend_round_trips_against_a_real_server() {
    let mut postgresql = PostgreSQL::default();
    postgresql.setup().await.expect("setup embedded postgres");
    postgresql.start().await.expect("start embedded postgres");
    postgresql
        .create_database("kai_remote_backend_test")
        .await
        .expect("create test database");
    let database_url = postgresql.settings().url("kai_remote_backend_test");

    kai_server::run_migrations(&database_url).await;
    let pool = kai_server::build_pool(&database_url);

    let token = "test-shared-token".to_string();
    let app = kai_server::routes::build(kai_server::state::AppState { pool }, token.clone());
    let listener = tokio::net::TcpListener::bind("127.0.0.1:0").await.unwrap();
    let addr = listener.local_addr().unwrap();
    tokio::spawn(async move {
        axum::serve(listener, app).await.unwrap();
    });

    let remote = RemoteBackend::new(format!("http://{addr}"), token);

    // --- Items ---
    let onion = remote.create_item("Onion").await.expect("create item");
    assert!(onion.is_perishable, "items default to perishable");
    let onion = remote
        .set_item_perishable(onion.id, false)
        .await
        .expect("set perishable");
    assert!(!onion.is_perishable);
    // Flip it back — a non-perishable ingredient is deliberately skipped
    // when a recipe expands onto a shopping list (see `expand_recipe`
    // server-side), and that's not what this test is checking below.
    let onion = remote
        .set_item_perishable(onion.id, true)
        .await
        .expect("reset perishable");
    let all_items = remote.list_items().await.expect("list items");
    assert!(all_items.iter().any(|i| i.id == onion.id));

    // --- SKUs (real Sku fixture, not a bare stub) ---
    let stored = remote
        .save_sku_to_item(onion.id, &fixture_sku())
        .await
        .expect("save sku");
    assert_eq!(stored.sku.sku, "144329");
    assert_eq!(stored.sku.price.sale_price, Some(3.5));
    let skus_for_item = remote.list_skus_for_item(onion.id).await.expect("list skus");
    assert_eq!(skus_for_item.len(), 1);

    // --- Tags ---
    let tag = remote.add_tag_to_item(onion.id, "Produce").await.expect("add tag");
    let tags_for_item = remote.list_tags_for_item(onion.id).await.expect("list tags");
    assert!(tags_for_item.iter().any(|t| t.id == tag.id));

    // --- Recipes + ingredients ---
    let soup = remote.create_recipe("Soup").await.expect("create recipe");
    remote
        .add_item_to_recipe(soup.id, onion.id)
        .await
        .expect("link onion to recipe");
    let ingredient = remote
        .set_recipe_item_quantity(soup.id, onion.id, Some(200.0), Some("g"))
        .await
        .expect("set quantity");
    assert_eq!(ingredient.amount, Some(200.0));
    let ingredients = remote
        .list_recipe_ingredients(soup.id)
        .await
        .expect("list ingredients");
    assert_eq!(ingredients.len(), 1);

    // --- Shopping list: expand the recipe, confirm the real merge/skip
    //     logic ran server-side (not something RemoteBackend does itself) ---
    let list = remote.create_shopping_list("Shop").await.expect("create list");
    let lines = remote
        .add_recipe_to_shopping_list(list.id, soup.id, None)
        .await
        .expect("expand recipe onto list");
    assert_eq!(lines.len(), 1);
    assert_eq!(lines[0].item_id, onion.id);

    let on_list = remote
        .list_shopping_list_items(list.id)
        .await
        .expect("list lines");
    assert_eq!(on_list.len(), 1);

    let omitted = remote
        .list_omitted_shopping_list_items(&[list.id])
        .await
        .expect("omission report");
    assert!(omitted.recipe_ingredients.is_empty(), "the only ingredient is already on the list");

    let cheapest = remote.cheapest_sku_id(onion.id).await.expect("cheapest sku");
    assert_eq!(cheapest, Some(stored.id));

    remote.remove_shopping_list_item(on_list[0].id).await.expect("remove line");

    // clear_shopping_list — the "Clear list" button's command. Re-add a
    // line first so there's something real to clear, and confirm the
    // list itself survives (distinct from delete_shopping_list below).
    remote
        .add_item_to_shopping_list(list.id, onion.id, Some(1.0), Some("count"))
        .await
        .expect("re-add a line to clear");
    remote.clear_shopping_list(list.id).await.expect("clear list");
    let after_clear = remote
        .list_shopping_list_items(list.id)
        .await
        .expect("list lines after clear");
    assert!(after_clear.is_empty(), "clear should remove every line");

    remote.delete_shopping_list(list.id).await.expect("delete list");

    // --- Settings (delivery fee) ---
    let fee = remote.get_delivery_fee().await.expect("get default delivery fee");
    assert_eq!(fee, 14.0, "defaults to Oscar's usual fee when unset");
    let updated = remote.set_delivery_fee(20.0).await.expect("set delivery fee");
    assert_eq!(updated, 20.0);
    assert_eq!(remote.get_delivery_fee().await.expect("re-read fee"), 20.0);

    // --- Cleanup, then confirm the guard: a still-linked item can't be
    //     deleted, but the error text comes back through intact ---
    let guard_err = remote.delete_item(onion.id).await.unwrap_err();
    assert!(guard_err.contains("Soup"), "guard error should name the blocking recipe: {guard_err}");
    remote.remove_item_from_recipe(soup.id, onion.id).await.expect("unlink");
    remote.delete_item(onion.id).await.expect("delete now unlinked item");
    remote.delete_recipe(soup.id).await.expect("delete recipe");

    // --- Auth: a wrong token should fail with the real 401, surfaced as
    //     a plain error string (kai-server's auth middleware returns a
    //     bare status code, no JSON body — RemoteBackend's fallback path
    //     is what's actually being exercised here) ---
    let wrong = RemoteBackend::new(format!("http://{addr}"), "not-the-real-token".to_string());
    let err = wrong.list_items().await.unwrap_err();
    assert!(err.contains("401"), "expected the 401 to surface in the error: {err}");

    postgresql.stop().await.ok();
}
