// `backend`/`db` are `pub` so `tests/remote_backend.rs` (an external
// integration test crate) can drive `RemoteBackend` and read the same
// `kai_shared`-backed types the real app does — see that file for why a
// real embedded Postgres + a real `kai-server` beats mocking the HTTP
// layer here.
pub mod backend;
mod commands;
pub mod db;
mod woolworths;
mod woolworths_cart;

use backend::ActiveBackend;
use std::sync::{Arc, Mutex};
use tauri::Manager;

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_updater::Builder::new().build())
        .plugin(tauri_plugin_process::init())
        .setup(|app| {
            let conn = db::init(app.handle())?;
            // Always managed regardless of local/remote mode — see
            // `backend::LocalConn`'s doc comment and CLAUDE.md's Phase B
            // notes for why this connection outlives whichever `Backend`
            // is currently active.
            let local_conn: backend::LocalConn = Arc::new(Mutex::new(conn));
            app.manage(local_conn.clone());

            let active = backend::resolve(&local_conn)?;
            app.manage(Mutex::new(active) as ActiveBackend);
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            woolworths::fetch_woolworths_sku,
            commands::create_item,
            commands::list_items,
            commands::save_sku_to_item,
            commands::list_skus_for_item,
            commands::update_item_name,
            commands::set_item_perishable,
            commands::set_item_image_url,
            commands::set_item_cheapest_by,
            commands::delete_item,
            commands::delete_sku,
            commands::set_sku_preferred,
            commands::refresh_sku,
            commands::refresh_skus_for_item,
            commands::list_tags,
            commands::list_tags_for_item,
            commands::add_tag_to_item,
            commands::remove_tag_from_item,
            commands::set_tag_emoji,
            commands::create_recipe,
            commands::list_recipes,
            commands::update_recipe_name,
            commands::set_recipe_image_url,
            commands::delete_recipe,
            commands::add_item_to_recipe,
            commands::remove_item_from_recipe,
            commands::list_recipe_ingredients,
            commands::set_recipe_item_quantity,
            commands::update_recipe_method,
            commands::update_recipe_servings,
            commands::update_recipe_source_url,
            commands::list_tags_for_recipe,
            commands::add_tag_to_recipe,
            commands::remove_tag_from_recipe,
            commands::create_shopping_list,
            commands::list_shopping_lists,
            commands::update_shopping_list_name,
            commands::delete_shopping_list,
            commands::list_shopping_list_items,
            commands::list_omitted_shopping_list_items,
            commands::add_item_to_shopping_list,
            commands::add_recipe_to_shopping_list,
            commands::set_shopping_list_recipe_quantity,
            commands::set_shopping_list_item_amount,
            commands::set_shopping_list_item_sku,
            commands::remove_shopping_list_item,
            commands::clear_shopping_list,
            commands::open_woolworths_login,
            commands::open_woolworths_cart,
            commands::woolworths_login_status,
            commands::woolworths_session_debug,
            commands::add_shopping_lists_to_cart,
            commands::get_delivery_fee,
            commands::set_delivery_fee,
            commands::get_backend_config,
            commands::set_backend_mode,
            commands::set_remote_config,
            commands::test_remote_connection,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
