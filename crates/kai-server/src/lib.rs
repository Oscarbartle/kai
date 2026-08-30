pub mod auth;
pub mod db;
pub mod error;
pub mod routes;
pub mod state;

refinery::embed_migrations!("./migrations");

/// Runs the embedded migrations on a single direct (non-pooled)
/// connection — simplest way to get the plain `&mut tokio_postgres::Client`
/// refinery wants. Exposed so both `main.rs` (startup) and the
/// integration tests (against a scratch database) can reuse it.
pub async fn run_migrations(database_url: &str) {
    let (mut client, connection) = tokio_postgres::connect(database_url, tokio_postgres::NoTls)
        .await
        .expect("Couldn't connect to Postgres to run migrations");
    tokio::spawn(async move {
        if let Err(e) = connection.await {
            eprintln!("Postgres migration connection error: {e}");
        }
    });
    migrations::runner()
        .run_async(&mut client)
        .await
        .expect("Migrations failed");
}

pub fn build_pool(database_url: &str) -> deadpool_postgres::Pool {
    let pg_config: tokio_postgres::Config =
        database_url.parse().expect("DATABASE_URL isn't a valid Postgres connection string");
    let manager = deadpool_postgres::Manager::from_config(
        pg_config,
        tokio_postgres::NoTls,
        deadpool_postgres::ManagerConfig {
            recycling_method: deadpool_postgres::RecyclingMethod::Fast,
        },
    );
    deadpool_postgres::Pool::builder(manager)
        .max_size(16)
        .build()
        .expect("Couldn't build the Postgres connection pool")
}
