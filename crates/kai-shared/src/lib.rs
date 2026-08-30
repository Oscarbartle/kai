//! Plain wire-format types shared between `src-tauri` (the desktop app,
//! talking to either local SQLite or a remote server) and `kai-server`
//! (the future Postgres-backed remote API — see CLAUDE.md's Phase B
//! notes). Every type here is exactly the JSON shape already sent to the
//! frontend today, moved out unchanged so a remote `Backend` impl can
//! deserialize the same shapes a local one produces, and so the server
//! can produce them too without depending on `rusqlite`.
//!
//! Deliberately just data + validation constants — no SQL, no `tauri`,
//! no `reqwest`. The SQL itself is *not* shared: SQLite and Postgres
//! need genuinely different queries in real places (see the Phase B
//! plan's dialect table), so `db::*` (SQLite) and `kai-server`'s own
//! modules (Postgres) each reimplement the same *rules* against their
//! own database, importing only the shapes and constants from here.

pub mod items;
pub mod recipe_items;
pub mod recipes;
pub mod shopping_list_items;
pub mod shopping_lists;
pub mod skus;
pub mod tags;
