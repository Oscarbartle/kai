//! What the mobile web app depends on, proven against a real embedded
//! Postgres and a real socket (same approach as `tests/http.rs`):
//!
//! - the built app is served at the site root *without* a token, since it
//!   has to load before anyone can type one in;
//! - every API route is still token-protected despite that;
//! - an unknown path 404s rather than returning `index.html` (a mistyped
//!   API route must not turn into an HTML page a JSON client chokes on);
//! - `/pantry` and `/recipe-book` return the whole screen's data in one
//!   request, in the shape the app reads.

use kai_server::state::AppState;
use postgresql_embedded::PostgreSQL;
use serde_json::Value;

#[tokio::test]
async fn static_app_and_bulk_endpoints() {
    // A stand-in for the built app — this test is about serving, not
    // about what's in the bundle.
    let dir = std::env::temp_dir().join(format!("kai-static-test-{}", std::process::id()));
    std::fs::create_dir_all(dir.join("assets")).unwrap();
    std::fs::write(dir.join("index.html"), "<!doctype html><title>Kai</title>").unwrap();
    std::fs::write(dir.join("manifest.webmanifest"), r#"{"name":"Kai"}"#).unwrap();
    std::fs::write(dir.join("assets").join("app.js"), "console.log('hi')").unwrap();

    let mut postgresql = PostgreSQL::default();
    postgresql.setup().await.expect("setup");
    postgresql.start().await.expect("start");
    postgresql.create_database("kai_thin_client_test").await.expect("create db");
    let database_url = postgresql.settings().url("kai_thin_client_test");

    kai_server::run_migrations(&database_url).await;
    let pool = kai_server::build_pool(&database_url);

    // Seed through the real db layer: two items (one tagged, one with a
    // SKU), and a recipe with a tag and an ingredient.
    let client = pool.get().await.unwrap();
    let onion = kai_server::db::items::create(&client, "Onion").await.unwrap();
    let apple = kai_server::db::items::create(&client, "apple").await.unwrap();
    kai_server::db::tags::add_to_item(&client, onion.id, "Veg").await.unwrap();
    let soup = kai_server::db::recipes::create(&client, "Soup").await.unwrap();
    kai_server::db::tags::add_to_recipe(&client, soup.id, "Quick").await.unwrap();
    kai_server::db::recipe_items::add(&client, soup.id, onion.id).await.unwrap();
    kai_server::db::recipe_items::set_quantity(&client, soup.id, onion.id, Some(2.0), Some("count"))
        .await
        .unwrap();
    let weekly = kai_server::db::shopping_lists::create(&client, "Weekly").await.unwrap();
    kai_server::db::shopping_lists::create(&client, "Empty").await.unwrap();
    kai_server::db::shopping_list_items::add_item(&client, weekly.id, onion.id, Some(3.0), Some("count"), None)
        .await
        .unwrap();
    drop(client);

    let token = "test-shared-token";
    let app = kai_server::routes::build(AppState { pool }, token.to_string());
    let app = kai_server::routes::with_static_files(app, &dir);

    let listener = tokio::net::TcpListener::bind("127.0.0.1:0").await.unwrap();
    let addr = listener.local_addr().unwrap();
    tokio::spawn(async move {
        axum::serve(listener, app).await.unwrap();
    });
    let base = format!("http://{addr}");
    let http = reqwest::Client::new();

    // --- The app loads with no token, and revalidates every time ---
    let index = http.get(format!("{base}/")).send().await.unwrap();
    assert_eq!(index.status(), 200, "the app itself must load without a token");
    assert_eq!(index.headers()["cache-control"], "no-cache");
    assert!(index.text().await.unwrap().contains("<title>Kai</title>"));

    let manifest = http.get(format!("{base}/manifest.webmanifest")).send().await.unwrap();
    assert_eq!(manifest.status(), 200);
    assert!(
        manifest.headers()["content-type"].to_str().unwrap().contains("manifest+json"),
        "manifest needs its own content type or installability checks can reject it"
    );

    assert_eq!(http.get(format!("{base}/assets/app.js")).send().await.unwrap().status(), 200);

    // --- ...but serving files didn't open up the API ---
    assert_eq!(http.get(format!("{base}/items")).send().await.unwrap().status(), 401);
    assert_eq!(http.get(format!("{base}/pantry")).send().await.unwrap().status(), 401);
    assert_eq!(http.get(format!("{base}/recipe-book")).send().await.unwrap().status(), 401);
    assert_eq!(http.get(format!("{base}/shopping")).send().await.unwrap().status(), 401);

    // --- An unknown path is a 404, not index.html with a 200 ---
    assert_eq!(http.get(format!("{base}/definitely-not-a-thing")).send().await.unwrap().status(), 404);

    // --- /pantry: alphabetical (case-insensitive), with tags per item ---
    let pantry: Value = http
        .get(format!("{base}/pantry"))
        .bearer_auth(token)
        .send()
        .await
        .unwrap()
        .json()
        .await
        .unwrap();
    let entries = pantry.as_array().expect("pantry is an array");
    assert_eq!(entries.len(), 2);
    assert_eq!(entries[0]["item"]["name"], "apple", "alphabetical, case-insensitive: apple before Onion");
    assert_eq!(entries[1]["item"]["name"], "Onion");
    assert_eq!(entries[0]["item"]["id"], apple.id);
    assert!(entries[0]["skus"].as_array().unwrap().is_empty());
    assert!(entries[0]["tags"].as_array().unwrap().is_empty());
    assert_eq!(entries[1]["tags"][0]["name"], "Veg");

    // --- /recipe-book: tags and ingredients included, so a card opens
    //     with no second request ---
    let book: Value = http
        .get(format!("{base}/recipe-book"))
        .bearer_auth(token)
        .send()
        .await
        .unwrap()
        .json()
        .await
        .unwrap();
    let recipes = book.as_array().expect("recipe book is an array");
    assert_eq!(recipes.len(), 1);
    assert_eq!(recipes[0]["recipe"]["name"], "Soup");
    assert_eq!(recipes[0]["tags"][0]["name"], "Quick");
    assert_eq!(recipes[0]["ingredients"][0]["name"], "Onion");
    assert_eq!(recipes[0]["ingredients"][0]["amount"], 2.0);
    assert_eq!(recipes[0]["ingredients"][0]["unit"], "count");

    // --- /shopping: every list with its lines, in one request ---
    let shopping: Value = http
        .get(format!("{base}/shopping"))
        .bearer_auth(token)
        .send()
        .await
        .unwrap()
        .json()
        .await
        .unwrap();
    let lists = shopping.as_array().expect("shopping is an array");
    assert_eq!(lists.len(), 2);
    let weekly_entry = lists.iter().find(|l| l["list"]["name"] == "Weekly").expect("Weekly list");
    assert_eq!(weekly_entry["list"]["id"], weekly.id);
    assert_eq!(weekly_entry["lines"][0]["item_name"], "Onion");
    assert_eq!(weekly_entry["lines"][0]["amount"], 3.0);
    assert_eq!(weekly_entry["lines"][0]["unit"], "count");
    let empty_entry = lists.iter().find(|l| l["list"]["name"] == "Empty").expect("Empty list");
    assert!(empty_entry["lines"].as_array().unwrap().is_empty());

    std::fs::remove_dir_all(&dir).ok();
    postgresql.stop().await.ok();
}
