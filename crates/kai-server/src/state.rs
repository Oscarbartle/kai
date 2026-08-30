#[derive(Clone)]
pub struct AppState {
    pub pool: deadpool_postgres::Pool,
}
