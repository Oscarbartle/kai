use deadpool_postgres::Pool;
use kai_server::state::AppState;

#[tokio::main]
async fn main() {
    // Loads a local `.env` if present (see .env.example) — harmless no-op
    // in Docker, where these come from the container's real environment
    // instead.
    dotenvy::dotenv().ok();

    let database_url = std::env::var("DATABASE_URL")
        .expect("DATABASE_URL must be set, e.g. postgres://kai:password@postgres:5432/kai");
    let shared_token = std::env::var("KAI_SHARED_TOKEN")
        .expect("KAI_SHARED_TOKEN must be set — the token the desktop app authenticates with");
    let port: u16 = std::env::var("PORT")
        .ok()
        .and_then(|p| p.parse().ok())
        .unwrap_or(8787);

    kai_server::run_migrations(&database_url).await;

    let pool: Pool = kai_server::build_pool(&database_url);
    let mut app = kai_server::routes::build(AppState { pool }, shared_token);

    // Optional: serve the built mobile web app from this folder (the
    // Docker image sets it). Unset = API only, exactly as before.
    if let Ok(dir) = std::env::var("KAI_STATIC_DIR") {
        println!("serving the mobile web app from {dir}");
        app = kai_server::routes::with_static_files(app, dir);
    }

    let listener = tokio::net::TcpListener::bind(("0.0.0.0", port))
        .await
        .unwrap_or_else(|e| panic!("Couldn't bind to port {port}: {e}"));
    println!("kai-server listening on :{port}");
    axum::serve(listener, app).await.expect("Server error");
}
