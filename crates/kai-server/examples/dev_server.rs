//! A throwaway, seeded kai-server for working on the mobile web app without
//! going near the real one: a fresh embedded Postgres (no Docker, nothing
//! installed), a handful of realistic items and recipes, and the built app
//! served from a folder — the same arrangement as production.
//!
//!     cd mobile && npm run build && cd ..
//!     cargo run -p kai-server --example dev_server
//!
//! Then open http://127.0.0.1:8799 and enter the token below (a made-up test
//! value for this throwaway database — it opens nothing real). Everything is
//! deleted when the process exits. An optional first argument overrides the
//! folder to serve (default `mobile/dist`).
//!
//! The seed leans on edge cases on purpose, so the UI gets exercised on more
//! than the happy path: an image that won't load, an item with no SKU (no
//! price), a special, a long name, a recipe with no image/servings/method,
//! fractional tsp/tbsp amounts, numbered and un-numbered methods, and a
//! source link that isn't a web address.

use kai_server::db::{items, recipe_items, recipes, skus, tags};
use kai_server::state::AppState;
use kai_shared::skus::{Sku, SkuPrice, SkuQuantity, SkuSize};
use postgresql_embedded::PostgreSQL;

const TOKEN: &str = "dev-token";
const PORT: u16 = 8799;

fn image(sku: &str) -> String {
    format!("https://assets.woolworths.com.au/images/2010/{sku}.jpg?impolicy=wowcdxwbjbx&w=900&h=900")
}

fn sku(code: &str, name: &str, sale: f64, was: Option<f64>, with_image: bool) -> Sku {
    Sku {
        provider: "woolworths".into(),
        sku: code.into(),
        name: name.into(),
        brand: None,
        variety: None,
        price: SkuPrice {
            original_price: Some(was.unwrap_or(sale)),
            sale_price: Some(sale),
            is_special: was.is_some(),
            ..Default::default()
        },
        size: SkuSize::default(),
        quantity: SkuQuantity { unit: "Each".into(), ..Default::default() },
        availability_status: Some("In Stock".into()),
        stock_level: None,
        images: if with_image { vec![image(code)] } else { vec![] },
        allergens: vec![],
        ingredients: vec![],
    }
}

#[tokio::main]
async fn main() {
    let static_dir = std::env::args().nth(1).unwrap_or_else(|| "mobile/dist".into());

    let mut pg = PostgreSQL::default();
    pg.setup().await.expect("set up embedded Postgres");
    pg.start().await.expect("start embedded Postgres");
    pg.create_database("kai_dev").await.expect("create database");
    let url = pg.settings().url("kai_dev");

    kai_server::run_migrations(&url).await;
    let pool = kai_server::build_pool(&url);
    seed(&pool.get().await.expect("pooled client")).await;

    let app = kai_server::routes::build(AppState { pool }, TOKEN.into());
    let app = kai_server::routes::with_static_files(app, &static_dir);

    let listener = tokio::net::TcpListener::bind(("127.0.0.1", PORT))
        .await
        .unwrap_or_else(|e| panic!("couldn't bind port {PORT}: {e}"));
    println!("serving {static_dir} + API at http://127.0.0.1:{PORT}  (token: {TOKEN})  — Ctrl-C to stop");

    axum::serve(listener, app)
        .with_graceful_shutdown(async {
            tokio::signal::ctrl_c().await.ok();
        })
        .await
        .expect("serve");
    pg.stop().await.ok();
}

async fn seed(c: &deadpool_postgres::Client) {
    // (name, tags, optional SKU: code, sku name, sale, was, image?)
    type Seed<'a> = (&'a str, &'a [&'a str], Option<(&'a str, &'a str, f64, Option<f64>, bool)>);
    let pantry: &[Seed] = &[
        ("Canned Tomatoes", &["Canned"], Some(("311488", "essentials diced tomatoes", 0.94, None, true))),
        ("Chicken Thighs", &["Fridge", "Meat"], Some(("57005", "chicken thighs skinless boneless", 26.5, None, true))),
        ("Brown Onion", &["Vegetable"], Some(("144329", "fresh vegetable onions brown", 2.18, None, true))),
        ("Colby Cheese", &["Dairy", "Fridge"], Some(("281810", "cheese colby 1kg", 13.59, Some(15.49), true))),
        ("Pasta Spirals", &["Pantry"], Some(("727848", "diamond pasta spirals 500g", 2.99, None, true))),
        ("Whittakers Chocolate Creamy Milk Block", &["Snacks"], Some(("266869", "whittakers creamy milk", 8.49, None, false))),
        // An SKU whose image won't load → the letter placeholder.
        ("Olive Oil", &["Pantry"], Some(("0000001", "extra virgin olive oil", 17.39, None, true))),
        // No SKU at all → "N/A" price, no image.
        ("Oregano", &["Herbs"], None),
        ("apple", &["Fruit"], Some(("0000002", "royal gala apples", 4.5, Some(5.9), false))),
        ("Salt", &["Herbs", "Pantry"], None),
    ];
    for (name, tag_names, sku_info) in pantry {
        let item = items::create(c, name).await.expect("create item");
        for t in *tag_names {
            tags::add_to_item(c, item.id, t).await.expect("tag item");
        }
        if let Some((code, sku_name, sale, was, img)) = sku_info {
            skus::save(c, item.id, &sku(code, sku_name, *sale, *was, *img)).await.expect("save sku");
        }
    }

    // Look the items back up by name for the recipes' ingredient links.
    let all = items::list(c).await.expect("list items");
    let id = |n: &str| all.iter().find(|i| i.name == n).unwrap_or_else(|| panic!("no item {n}")).id;

    // 1. A fully-filled recipe: image, servings, source, numbered method.
    let pasta = recipes::create(c, "Tomato Pasta").await.unwrap();
    recipes::update_servings(c, pasta.id, Some(4)).await.unwrap();
    recipes::set_image_url(
        c,
        pasta.id,
        Some("https://www.allrecipes.com/thmb/A0RlVFdwsIq-8mNXPQbOTGCRyWo=/1500x0/filters:no_upscale():max_bytes(150000):strip_icc()/AR-130358-worlds-best-pasta-sauce-ddmfs-2x1-cd6886274bc3482eae3a557cc7270dcb.jpg"),
    )
    .await
    .unwrap();
    recipes::update_source_url(c, pasta.id, "https://example.com/tomato-pasta").await.unwrap();
    recipes::update_method(
        c,
        pasta.id,
        "1. Add olive oil to pan and bring to heat. Add onions and crushed garlic and cook until there is a little colour.\n2. Add tomato paste and wine and cook off the alcohol.\n3. Add canned tomatoes, oregano, salt, and pepper, then reduce until thick. Add water to extend cooking time and deepen the flavour.\n4. Serve with pasta and cheese.",
    )
    .await
    .unwrap();
    tags::add_to_recipe(c, pasta.id, "Base").await.unwrap();
    tags::add_to_recipe(c, pasta.id, "Quick").await.unwrap();
    for (item, amount, unit) in [
        ("Brown Onion", Some(1.0), "count"),
        ("Canned Tomatoes", Some(4.0), "count"),
        ("Colby Cheese", Some(125.0), "g"),
        ("Pasta Spirals", Some(1.0), "count"),
        ("Olive Oil", Some(2.0), "tbsp"),
        ("Oregano", Some(1.5), "tsp"),
        ("Salt", Some(0.5), "tsp"),
    ] {
        recipe_items::add(c, pasta.id, id(item)).await.unwrap();
        recipe_items::set_quantity(c, pasta.id, id(item), amount, Some(unit)).await.unwrap();
    }

    // 2. An un-numbered, one-step-per-line method, and an ingredient with
    //    no amount set.
    let curry = recipes::create(c, "Thai Red Curry with Chicken").await.unwrap();
    recipes::update_servings(c, curry.id, Some(4)).await.unwrap();
    recipes::update_method(
        c,
        curry.id,
        "Heat oil in a large heavy based skillet over medium high heat.\nAdd curry paste and cook for about 2 minutes so it dries out.\nAdd chicken broth and stir to dissolve paste. Simmer rapidly for 3 minutes or until liquid reduces by half.\nAdd coconut milk, sugar and fish sauce. Stir, then add chicken.\nSimmer for about 8-10 minutes until the sauce reduces and the chicken is cooked through.\nServe over jasmine rice.",
    )
    .await
    .unwrap();
    for (item, amount, unit) in [
        ("Chicken Thighs", Some(600.0), "g"),
        ("Brown Onion", None, "count"),
        ("Salt", Some(0.25), "tsp"),
    ] {
        recipe_items::add(c, curry.id, id(item)).await.unwrap();
        recipe_items::set_quantity(c, curry.id, id(item), amount, Some(unit)).await.unwrap();
    }

    // 3. Almost nothing filled in — no image, servings, method or tags.
    let pizza = recipes::create(c, "Pizza").await.unwrap();
    recipe_items::add(c, pizza.id, id("Colby Cheese")).await.unwrap();
    recipe_items::set_quantity(c, pizza.id, id("Colby Cheese"), Some(300.0), Some("g")).await.unwrap();

    // 4. A source "link" that isn't a web address, and a single-block method.
    let salad = recipes::create(c, "Quick Salad").await.unwrap();
    recipes::update_source_url(c, salad.id, "javascript:alert(1)").await.unwrap();
    recipes::update_method(c, salad.id, "Chop everything and toss it together.").await.unwrap();
}
