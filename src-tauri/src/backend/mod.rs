//! The local/remote switch — see CLAUDE.md's Phase B notes. `commands.rs`
//! calls through `Backend` instead of `db::*` directly, so it doesn't
//! know or care whether it's talking to local SQLite (`LocalBackend`) or
//! a remote Postgres-backed server (`RemoteBackend`, added in a later
//! stage — this stage is local-only, zero behavior change from before
//! `Backend` existed).
//!
//! One sub-trait per `db/*.rs` module, mirroring that existing
//! repository-module boundary file-for-file. Method names match the
//! `commands.rs` function that calls each, one-for-one — this is what
//! lets every sub-trait combine into one blanket `Backend` without ever
//! colliding on a method name (no shared `create`/`get`/`list` across
//! domains), and makes the `commands.rs` rewrite read as "call the
//! same-named backend method" rather than a real rename.

mod items;
mod local;
mod recipe_items;
mod recipes;
mod remote;
mod settings;
mod shopping_list_items;
mod shopping_lists;
mod skus;
mod tags;

pub use items::ItemsBackend;
pub use local::LocalBackend;
pub use recipe_items::RecipeItemsBackend;
pub use recipes::RecipesBackend;
pub use remote::RemoteBackend;
pub use settings::SettingsBackend;
pub use shopping_list_items::ShoppingListItemsBackend;
pub use shopping_lists::ShoppingListsBackend;
pub use skus::SkusBackend;
pub use tags::TagsBackend;

/// Everything a `commands.rs` function might need, regardless of whether
/// it's actually backed by local SQLite or a remote server.
pub trait Backend:
    ItemsBackend
    + SkusBackend
    + TagsBackend
    + RecipesBackend
    + RecipeItemsBackend
    + ShoppingListsBackend
    + ShoppingListItemsBackend
    + SettingsBackend
    + Send
    + Sync
{
}

impl<T> Backend for T where
    T: ItemsBackend
        + SkusBackend
        + TagsBackend
        + RecipesBackend
        + RecipeItemsBackend
        + ShoppingListsBackend
        + ShoppingListItemsBackend
        + SettingsBackend
        + Send
        + Sync
{
}

/// App state: the currently-active backend, swappable at runtime when
/// the user changes the local/remote setting (see `set_backend_mode`/
/// `set_remote_config` in `commands.rs`). A plain `std::sync::Mutex`, same
/// shape as the `Db` mutex this replaces — locked only long enough to
/// clone the `Arc`, never held across an `.await`.
pub type ActiveBackend = std::sync::Mutex<std::sync::Arc<dyn Backend>>;

/// The local SQLite connection, kept separate from `ActiveBackend` and
/// always managed regardless of mode — `backend_mode`/`remote_url`/
/// `remote_token` themselves live in this connection's `settings` table
/// (see `db::settings`), since they configure which backend to use and
/// can't themselves live behind the backend they configure. Also what
/// lets a mode switch back to "local" show the exact same data it had
/// before switching away — this connection, and the file behind it,
/// never closes just because `ActiveBackend` briefly points elsewhere.
pub type LocalConn = std::sync::Arc<std::sync::Mutex<rusqlite::Connection>>;

/// Builds the backend that matches the currently-saved settings — local
/// SQLite (via the shared `LocalConn`) or remote (a fresh `RemoteBackend`
/// pointed at the saved URL/token). Called once at startup and again by
/// `set_backend_mode`/`set_remote_config` every time either setting
/// changes, so `ActiveBackend` is always rebuilt from the same single
/// source of truth rather than patched in place.
pub fn resolve(local_conn: &LocalConn) -> Result<std::sync::Arc<dyn Backend>, String> {
    let config = {
        let conn = local_conn.lock().map_err(|e| e.to_string())?;
        crate::db::settings::get_backend_config(&conn)?
    };
    Ok(if config.mode == "remote" {
        let url = config
            .remote_url
            .ok_or("Remote mode is set but no remote server URL is configured yet")?;
        std::sync::Arc::new(RemoteBackend::new(url, config.remote_token.unwrap_or_default()))
    } else {
        std::sync::Arc::new(LocalBackend::new(local_conn.clone()))
    })
}
