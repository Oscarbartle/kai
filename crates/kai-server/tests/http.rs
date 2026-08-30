//! Exercises the actual HTTP surface — routing, JSON (de)serialization,
//! and the auth middleware — none of which `tests/lifecycle.rs` touches
//! (that one calls `db::*` directly). Real embedded Postgres, real
//! `axum::serve`, real `reqwest` calls over a real TCP socket.

use kai_server::state::AppState;
use postgresql_embedded::PostgreSQL;
use serde_json::{json, Value};

#[tokio::test]
async fn http_surface_and_auth() {
    let mut postgresql = PostgreSQL::default();
    postgresql.setup().await.expect("setup");
    postgresql.start().await.expect("start");
    postgresql.create_database("kai_http_test").await.expect("create db");
    let database_url = postgresql.settings().url("kai_http_test");

    kai_server::run_migrations(&database_url).await;
    let pool = kai_server::build_pool(&database_url);

    let token = "test-shared-token".to_string();
    let app = kai_server::routes::build(AppState { pool }, token.clone());

    let listener = tokio::net::TcpListener::bind("127.0.0.1:0").await.unwrap();
    let addr = listener.local_addr().unwrap();
    tokio::spawn(async move {
        axum::serve(listener, app).await.unwrap();
    });
    let base = format!("http://{addr}");
    let http = reqwest::Client::new();

    // /health needs no token at all.
    let health: Value = http
        .get(format!("{base}/health"))
        .send()
        .await
        .expect("health request")
        .json()
        .await
        .expect("health json");
    assert_eq!(health, json!({ "ok": true }));

    // Everything else does — no header at all is rejected.
    let unauthed = http.get(format!("{base}/items")).send().await.expect("unauthed request");
    assert_eq!(unauthed.status(), 401);

    // Wrong token is rejected too, not just a missing one.
    let wrong_token = http
        .get(format!("{base}/items"))
        .bearer_auth("not-the-real-token")
        .send()
        .await
        .expect("wrong-token request");
    assert_eq!(wrong_token.status(), 401);

    // /status is what the app's "Test connection" button hits — proves
    // reachability *and* the token in one call.
    let status = http
        .get(format!("{base}/status"))
        .bearer_auth(&token)
        .send()
        .await
        .expect("status request");
    assert_eq!(status.status(), 200);

    // A real authenticated round trip: create an item over HTTP, read it
    // back, confirm the JSON shape matches what the desktop app expects
    // (snake_case field names, matching kai_shared::items::Item exactly).
    let created: Value = http
        .post(format!("{base}/items"))
        .bearer_auth(&token)
        .json(&json!({ "name": "Milk" }))
        .send()
        .await
        .expect("create item request")
        .json()
        .await
        .expect("create item json");
    assert_eq!(created["name"], "Milk");
    assert_eq!(created["is_perishable"], true);
    let item_id = created["id"].as_i64().expect("item id");

    let listed: Value = http
        .get(format!("{base}/items"))
        .bearer_auth(&token)
        .send()
        .await
        .expect("list items request")
        .json()
        .await
        .expect("list items json");
    let items = listed.as_array().expect("items array");
    assert!(items.iter().any(|i| i["id"] == item_id));

    postgresql.stop().await.ok();
}
