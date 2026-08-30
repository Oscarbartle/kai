//! SQLite persistence.
//!
//! Kept deliberately plain: standard SQL, no SQLite-only features, all
//! access behind the repository modules (`items`, `skus`) rather than
//! raw queries in Tauri commands. If this ever moves behind a remote API
//! (see CLAUDE.md — Unraid/Postgres later), that's a swap at the
//! repository boundary, not a rewrite of the schema or the commands.

pub mod items;
pub mod recipe_items;
pub mod recipes;
pub mod settings;
pub mod shopping_list_items;
pub mod shopping_lists;
pub mod skus;
pub mod tags;

use rusqlite::Connection;
use rusqlite_migration::{Migrations, M};
use std::sync::Mutex;
use tauri::{AppHandle, Manager};

pub type Db = Mutex<Connection>;

fn migrations() -> Migrations<'static> {
    Migrations::new(vec![
        M::up(
            "
            CREATE TABLE items (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                name       TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE skus (
                id                   INTEGER PRIMARY KEY AUTOINCREMENT,
                item_id              INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
                provider             TEXT NOT NULL,
                sku                  TEXT NOT NULL,
                name                 TEXT NOT NULL,
                brand                TEXT,
                variety              TEXT,
                original_price       REAL,
                sale_price           REAL,
                is_special           INTEGER NOT NULL DEFAULT 0,
                save_percentage      REAL,
                cup_price            REAL,
                cup_measure          TEXT,
                package_type         TEXT,
                volume_size          TEXT,
                availability_status  TEXT,
                stock_level          INTEGER,
                images               TEXT NOT NULL DEFAULT '[]',
                allergens            TEXT NOT NULL DEFAULT '[]',
                ingredients          TEXT NOT NULL DEFAULT '[]',
                created_at           TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at           TEXT NOT NULL DEFAULT (datetime('now')),
                UNIQUE(item_id, provider, sku)
            );
            ",
        ),
        // Tags: normalized rather than a JSON column on items, so tags can
        // be listed/reused/autocompleted and (later) filtered on directly
        // rather than living as opaque text.
        M::up(
            "
            CREATE TABLE tags (
                id   INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE COLLATE NOCASE
            );

            CREATE TABLE item_tags (
                item_id INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
                tag_id  INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
                PRIMARY KEY (item_id, tag_id)
            );
            ",
        ),
        // Drives shopping-list generation later: perishable items (veg,
        // milk) get re-added most trips, non-perishable ones (salt,
        // spices) shouldn't be. A dedicated typed column rather than a
        // tag, since it's meant to be read by logic, not just displayed.
        // Defaults true — most grocery items are bought regularly; the
        // exceptions are the ones worth flagging.
        M::up("ALTER TABLE items ADD COLUMN is_perishable INTEGER NOT NULL DEFAULT 1;"),
        M::up(
            "
            ALTER TABLE skus ADD COLUMN promotion_start_date TEXT;
            ALTER TABLE skus ADD COLUMN promotion_end_date TEXT;
            ",
        ),
        // How the SKU is actually purchased ("Each" vs "Kg", per
        // Woolworths' own field) plus the API's min/max/increment for
        // that unit — enables rounding a recipe's needed quantity to
        // something actually orderable later, not just a yes/no flag.
        M::up(
            "
            ALTER TABLE skus ADD COLUMN unit TEXT NOT NULL DEFAULT 'Each';
            ALTER TABLE skus ADD COLUMN quantity_min REAL;
            ALTER TABLE skus ADD COLUMN quantity_max REAL;
            ALTER TABLE skus ADD COLUMN quantity_increment REAL;
            ",
        ),
        // Some SKUs (loose onions, etc.) let the shopper choose weight
        // OR count at add-to-cart time on Woolworths' own site — `unit`
        // above only captures the default. average_weight_per_unit is
        // the conversion factor between the two modes when this is set.
        M::up(
            "
            ALTER TABLE skus ADD COLUMN supports_both_units INTEGER NOT NULL DEFAULT 0;
            ALTER TABLE skus ADD COLUMN average_weight_per_unit REAL;
            ",
        ),
        // Recipes: same bare "name only" starting slice as Item was —
        // ingredients/steps/etc are a separate future round once this
        // basic create/rename/delete shell is confirmed working.
        M::up(
            "
            CREATE TABLE recipes (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                name       TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            ",
        ),
        // Deliberately just a link for now — no quantity/unit. Oscar
        // wants a proper unit-conversion layer (recipes stated in
        // cups/tsp/g, shopping list figuring out what's actually
        // orderable) before quantities are worth storing; adding a
        // half-considered amount+unit column now would just get
        // replaced. See CLAUDE.md.
        M::up(
            "
            CREATE TABLE recipe_items (
                recipe_id INTEGER NOT NULL REFERENCES recipes(id) ON DELETE CASCADE,
                item_id   INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
                PRIMARY KEY (recipe_id, item_id)
            );
            ",
        ),
        // Short-lived: per-step rows, immediately superseded below by a
        // single method text box (simpler — reversed before this ever
        // shipped anywhere). Kept as its own migration rather than
        // edited in place since it may already be applied to a running
        // dev database; the next migration undoes it cleanly instead.
        M::up(
            "
            CREATE TABLE recipe_steps (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                recipe_id  INTEGER NOT NULL REFERENCES recipes(id) ON DELETE CASCADE,
                position   INTEGER NOT NULL,
                text       TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            ",
        ),
        // The method, as a single freeform text box instead — simpler,
        // matches how Oscar actually wants to write a recipe out.
        M::up(
            "
            DROP TABLE recipe_steps;
            ALTER TABLE recipes ADD COLUMN method TEXT;
            ",
        ),
        // Quantities, deliberately narrow: only `g`/`mL` (real,
        // shopping-relevant amounts) or `tsp`/`tbsp` (nominal — cooking
        // reference only, never touch shopping-list math). No cup, no
        // arbitrary units, no density/mass<->volume conversion needed as
        // a result — that was the genuinely hard, long-tail part of a
        // general conversion layer, and this sidesteps it entirely. Both
        // columns stay nullable: a link can exist with no quantity set
        // yet. `unit` is validated in Rust (recipe_items::VALID_UNITS),
        // not a DB CHECK constraint, since the nominal set may grow
        // later (see CLAUDE.md).
        M::up(
            "
            ALTER TABLE recipe_items ADD COLUMN amount REAL;
            ALTER TABLE recipe_items ADD COLUMN unit TEXT;
            ",
        ),
        // servings: what the ingredient amounts above are actually for —
        // needed to scale a recipe before it hits a shopping list later.
        // source_url: where the recipe came from, for reference.
        M::up(
            "
            ALTER TABLE recipes ADD COLUMN servings INTEGER;
            ALTER TABLE recipes ADD COLUMN source_url TEXT;
            ",
        ),
        // Recipe tags reuse the same `tags` table Items already use
        // (shared vocabulary — "quick"/"vegetarian" makes sense on
        // either) rather than a separate recipe-only tag pool.
        M::up(
            "
            CREATE TABLE recipe_tags (
                recipe_id INTEGER NOT NULL REFERENCES recipes(id) ON DELETE CASCADE,
                tag_id    INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
                PRIMARY KEY (recipe_id, tag_id)
            );
            ",
        ),
        // Shopping lists: named, multiple, same pattern as Items/Recipes.
        // Each line is a resolved item + amount/unit (g/mL/count only —
        // same rule as recipe_items) + the chosen SKU to buy, defaulting
        // to the cheapest linked one (by cup_price) but swappable. No
        // uniqueness constraint on (list_id, item_id): merging identical
        // items onto one line (same unit) is handled in Rust when adding
        // a recipe/item, not enforced by the schema — a mismatched-unit
        // add for an item already on the list becomes its own line
        // rather than something the DB has to reject or coerce.
        M::up(
            "
            CREATE TABLE shopping_lists (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                name       TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE shopping_list_items (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                list_id    INTEGER NOT NULL REFERENCES shopping_lists(id) ON DELETE CASCADE,
                item_id    INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
                amount     REAL,
                unit       TEXT,
                sku_id     INTEGER REFERENCES skus(id) ON DELETE SET NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            ",
        ),
        // Optional user-supplied image link, shown instead of a SKU's
        // own image on the item widget/detail view. Nullable — falls
        // back to the cheapest/first linked SKU's image (see
        // `db::skus`) when unset, same "flag, don't guess" rule as
        // everywhere else: no attempt to auto-pick or scrape an image.
        M::up("ALTER TABLE items ADD COLUMN image_url TEXT;"),
        // Same idea as items.image_url — user-supplied, no auto-picking.
        M::up("ALTER TABLE recipes ADD COLUMN image_url TEXT;"),
        // Tracks which recipe (if any) a line came from, so the new /app
        // UI's shopping-list widget can re-group a recipe's lines back
        // under one card after reopening the list — previously that
        // grouping only survived in-session. ON DELETE SET NULL rather
        // than CASCADE: deleting the recipe later shouldn't delete real
        // shopping-list content, just lose the (cosmetic) grouping tag.
        // Nullable, so plain item-drops (not from a recipe) just leave
        // it unset — see `shopping_list_items::add_item`'s merge rule
        // for how a line loses this tag if it later merges with a
        // differently-sourced add.
        M::up(
            "ALTER TABLE shopping_list_items
             ADD COLUMN source_recipe_id INTEGER REFERENCES recipes(id) ON DELETE SET NULL;",
        ),
        // Which metric the shopping-list auto-pick compares this item's
        // SKUs by — 'total' (plain sale_price — what you'd actually pay,
        // the default) or 'unit' (cup_price — $/kg or $/L, the better
        // per-pack-size comparison for an item where that's what
        // actually matters). Per-item rather than global: reasonable
        // defaults differ by item (bulk pantry staples vs. one-off
        // produce), not something one global rule gets right for
        // everything. Validated in Rust (items::VALID_CHEAPEST_BY), not
        // a DB constraint, matching recipe_items::VALID_UNITS.
        M::up("ALTER TABLE items ADD COLUMN cheapest_by TEXT NOT NULL DEFAULT 'total';"),
        // A user-picked override that trumps cheapest_by entirely for
        // the shopping-list auto-pick — a star on the SKU widget in the
        // item detail page. At most one true per item, enforced in Rust
        // (db::skus::set_preferred clears any other before setting a
        // new one), not a DB constraint — SQLite has no easy partial
        // unique index across a boolean+item_id pair without more
        // ceremony than this warrants.
        M::up("ALTER TABLE skus ADD COLUMN is_preferred INTEGER NOT NULL DEFAULT 0;"),
        // Flat key-value store for small app-wide preferences (see
        // db::settings) — first use is the Woolworths delivery fee shown
        // alongside a combined shopping-list total, but deliberately
        // generic rather than a dedicated column so future one-off
        // settings don't each need their own migration.
        M::up(
            "
            CREATE TABLE settings (
                key   TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            ",
        ),
        // A user-picked emoji override for a tag, shown on the Tags
        // sidebar's toggle buttons only (not the tag pills on item/recipe
        // cards — those stay plain text). Nullable: unset means "use the
        // auto-picked one" (a client-side keyword guess off the tag's
        // name, see +page.svelte's autoEmojiForTag — no need to persist
        // a guess that's cheap to recompute and would just go stale if
        // the guessing logic ever improves).
        M::up("ALTER TABLE tags ADD COLUMN emoji TEXT;"),
    ])
}

/// Opens (creating if needed) the SQLite database in the app's data
/// directory and brings it up to the latest migration.
pub fn init(app: &AppHandle) -> Result<Connection, String> {
    let dir = app
        .path()
        .app_data_dir()
        .map_err(|e| format!("Couldn't resolve app data dir: {e}"))?;
    std::fs::create_dir_all(&dir).map_err(|e| format!("Couldn't create app data dir: {e}"))?;

    let db_path = dir.join("kai.db");
    let mut conn =
        Connection::open(&db_path).map_err(|e| format!("Couldn't open database: {e}"))?;

    conn.pragma_update(None, "foreign_keys", true)
        .map_err(|e| format!("Couldn't enable foreign keys: {e}"))?;

    migrations()
        .to_latest(&mut conn)
        .map_err(|e| format!("Migration failed: {e}"))?;

    Ok(conn)
}
