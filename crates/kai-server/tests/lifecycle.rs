//! Real end-to-end lifecycle test against a genuine (embedded, ephemeral)
//! Postgres instance — no Docker needed to run this. Exercises the exact
//! path this whole Phase B effort is for: create an item, link a recipe
//! ingredient, expand a recipe onto a shopping list, confirm the
//! non-perishable-skip and omission-report rules carried over correctly
//! from the SQLite side.

use kai_server::db;
use postgresql_embedded::PostgreSQL;

#[tokio::test]
async fn full_lifecycle() {
    let mut postgresql = PostgreSQL::default();
    postgresql.setup().await.expect("Couldn't set up embedded Postgres");
    postgresql.start().await.expect("Couldn't start embedded Postgres");
    let database_name = "kai_test";
    postgresql
        .create_database(database_name)
        .await
        .expect("Couldn't create test database");
    let database_url = postgresql.settings().url(database_name);

    kai_server::run_migrations(&database_url).await;
    let pool = kai_server::build_pool(&database_url);
    let client = pool.get().await.expect("Couldn't get a pooled client");

    // --- Items ---
    let onion = db::items::create(&client, "Onion").await.expect("create onion");
    assert!(onion.is_perishable, "items default to perishable");

    let salt = db::items::create(&client, "Salt").await.expect("create salt");
    db::items::set_perishable(&client, salt.id, false)
        .await
        .expect("mark salt non-perishable");

    // --- Recipe + ingredients ---
    let soup = db::recipes::create(&client, "Soup").await.expect("create recipe");
    db::recipe_items::add(&client, soup.id, onion.id).await.expect("link onion");
    db::recipe_items::add(&client, soup.id, salt.id).await.expect("link salt");
    db::recipe_items::set_quantity(&client, soup.id, onion.id, Some(200.0), Some("g"))
        .await
        .expect("set onion quantity");
    db::recipe_items::set_quantity(&client, soup.id, salt.id, Some(5.0), Some("g"))
        .await
        .expect("set salt quantity");

    let ingredients = db::recipe_items::list_for_recipe(&client, soup.id)
        .await
        .expect("list ingredients");
    assert_eq!(ingredients.len(), 2, "both ingredients linked");

    // --- Shopping list: add the recipe, confirm the non-perishable skip ---
    let list = db::shopping_lists::create(&client, "Shop")
        .await
        .expect("create shopping list");
    let lines = db::shopping_list_items::add_recipe(&client, list.id, soup.id, None)
        .await
        .expect("expand recipe onto list");
    assert_eq!(
        lines.len(),
        1,
        "only the perishable ingredient (onion) should land on the list, salt is skipped"
    );
    assert_eq!(lines[0].item_id, onion.id);
    assert_eq!(lines[0].amount, Some(200.0));

    let on_list = db::shopping_list_items::list_for_list(&client, list.id)
        .await
        .expect("list lines");
    assert_eq!(on_list.len(), 1);

    // --- Omission report: salt should be flagged as a skipped ingredient ---
    let report = db::shopping_list_items::list_omitted(&client, &[list.id])
        .await
        .expect("list omitted");
    assert_eq!(report.recipe_ingredients.len(), 1, "salt should be flagged");
    assert_eq!(report.recipe_ingredients[0].item_id, salt.id);
    assert_eq!(report.recipe_ingredients[0].recipe_name, "Soup");

    // --- Clear list: empties lines but the list itself survives ---
    db::shopping_list_items::clear(&client, list.id).await.expect("clear list");
    let on_list_after_clear = db::shopping_list_items::list_for_list(&client, list.id)
        .await
        .expect("list lines after clear");
    assert!(on_list_after_clear.is_empty(), "clear should remove every line");
    let list_still_exists = db::shopping_lists::get(&client, list.id).await;
    assert!(list_still_exists.is_ok(), "the list itself should survive a clear");

    // Put a line back — the cascade-delete check further down needs a
    // real line to verify gets removed, not an already-empty list left
    // over from the clear test just above.
    db::shopping_list_items::add_item(&client, list.id, onion.id, Some(200.0), Some("g"), None)
        .await
        .expect("re-add onion after clearing");

    // --- cheapest_sku_id with no SKUs at all yields None, not an error ---
    let cheapest = db::shopping_list_items::cheapest_sku_id(&client, onion.id)
        .await
        .expect("cheapest_sku_id shouldn't error with no SKUs");
    assert_eq!(cheapest, None);

    // --- delete_item's guard equivalent: an item still linked to a
    //     recipe should be reported as in-use ---
    let recipes_using_onion = db::recipe_items::list_recipes_for_item(&client, onion.id)
        .await
        .expect("list recipes for item");
    assert_eq!(recipes_using_onion, vec!["Soup".to_string()]);

    // Unlink, then delete should succeed cleanly.
    db::recipe_items::remove(&client, soup.id, onion.id)
        .await
        .expect("unlink onion");
    db::items::delete(&client, onion.id).await.expect("delete onion");

    // The shopping-list line survives the item's recipe-unlink (it's a
    // separate row) but does get cleaned up once the item itself is
    // deleted, via ON DELETE CASCADE.
    let on_list_after_delete = db::shopping_list_items::list_for_list(&client, list.id)
        .await
        .expect("list lines after delete");
    assert!(on_list_after_delete.is_empty(), "cascade delete should remove the line");

    postgresql.stop().await.ok();
}
