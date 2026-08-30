//! Postgres port of `src-tauri/src/db/skus.rs`. `images`/`allergens`/
//! `ingredients` are `JSONB` here (vs. JSON-as-TEXT in SQLite) — decoded
//! straight into `Vec<String>` via `tokio-postgres`'s serde_json support,
//! no manual (de)serialization step needed.

use deadpool_postgres::Client;
use kai_shared::skus::{Sku, SkuPrice, SkuQuantity, SkuSize, StoredSku};
use serde_json::Value as Json;

const SELECT_COLUMNS: &str = "
    id, item_id, provider, sku, name, brand, variety,
    original_price, sale_price, is_special, save_percentage,
    promotion_start_date, promotion_end_date,
    cup_price, cup_measure, package_type, volume_size,
    unit, quantity_min, quantity_max, quantity_increment,
    supports_both_units, average_weight_per_unit,
    availability_status, stock_level, images, allergens, ingredients,
    is_preferred
";

fn json_strings(v: Json) -> Vec<String> {
    v.as_array()
        .map(|arr| arr.iter().filter_map(|s| s.as_str().map(str::to_string)).collect())
        .unwrap_or_default()
}

fn row_to_sku(row: &tokio_postgres::Row) -> StoredSku {
    StoredSku {
        id: row.get(0),
        item_id: row.get(1),
        is_preferred: row.get(28),
        sku: Sku {
            provider: row.get(2),
            sku: row.get(3),
            name: row.get(4),
            brand: row.get(5),
            variety: row.get(6),
            price: SkuPrice {
                original_price: row.get(7),
                sale_price: row.get(8),
                is_special: row.get(9),
                save_percentage: row.get(10),
                promotion_start_date: row.get(11),
                promotion_end_date: row.get(12),
            },
            size: SkuSize {
                cup_price: row.get(13),
                cup_measure: row.get(14),
                package_type: row.get(15),
                volume_size: row.get(16),
            },
            quantity: SkuQuantity {
                unit: row.get(17),
                min: row.get(18),
                max: row.get(19),
                increment: row.get(20),
                supports_both_each_and_kg: row.get(21),
                average_weight_per_unit: row.get(22),
            },
            availability_status: row.get(23),
            stock_level: row.get(24),
            images: json_strings(row.get(25)),
            allergens: json_strings(row.get(26)),
            ingredients: json_strings(row.get(27)),
        },
    }
}

pub async fn get(client: &Client, id: i64) -> Result<StoredSku, String> {
    let row = client
        .query_opt(&format!("SELECT {SELECT_COLUMNS} FROM skus WHERE id = $1"), &[&id])
        .await
        .map_err(|e| format!("Couldn't load SKU {id}: {e}"))?
        .ok_or_else(|| format!("No SKU with id {id}"))?;
    Ok(row_to_sku(&row))
}

/// Persists a fetched `Sku` against an item. Re-saving the same
/// provider+sku pair for the same item updates the cached fields
/// instead of creating a duplicate row.
pub async fn save(client: &Client, item_id: i64, sku: &Sku) -> Result<StoredSku, String> {
    let images = Json::from(sku.images.clone());
    let allergens = Json::from(sku.allergens.clone());
    let ingredients = Json::from(sku.ingredients.clone());

    let row = client
        .query_one(
            "INSERT INTO skus (
                item_id, provider, sku, name, brand, variety,
                original_price, sale_price, is_special, save_percentage,
                promotion_start_date, promotion_end_date,
                cup_price, cup_measure, package_type, volume_size,
                unit, quantity_min, quantity_max, quantity_increment,
                supports_both_units, average_weight_per_unit,
                availability_status, stock_level, images, allergens, ingredients,
                updated_at
            ) VALUES (
                $1, $2, $3, $4, $5, $6,
                $7, $8, $9, $10,
                $11, $12,
                $13, $14, $15, $16,
                $17, $18, $19, $20,
                $21, $22,
                $23, $24, $25, $26, $27,
                now()
            )
            ON CONFLICT (item_id, provider, sku) DO UPDATE SET
                name = excluded.name,
                brand = excluded.brand,
                variety = excluded.variety,
                original_price = excluded.original_price,
                sale_price = excluded.sale_price,
                is_special = excluded.is_special,
                save_percentage = excluded.save_percentage,
                promotion_start_date = excluded.promotion_start_date,
                promotion_end_date = excluded.promotion_end_date,
                cup_price = excluded.cup_price,
                cup_measure = excluded.cup_measure,
                package_type = excluded.package_type,
                volume_size = excluded.volume_size,
                unit = excluded.unit,
                quantity_min = excluded.quantity_min,
                quantity_max = excluded.quantity_max,
                quantity_increment = excluded.quantity_increment,
                supports_both_units = excluded.supports_both_units,
                average_weight_per_unit = excluded.average_weight_per_unit,
                availability_status = excluded.availability_status,
                stock_level = excluded.stock_level,
                images = excluded.images,
                allergens = excluded.allergens,
                ingredients = excluded.ingredients,
                updated_at = now()
            RETURNING id",
            &[
                &item_id,
                &sku.provider,
                &sku.sku,
                &sku.name,
                &sku.brand,
                &sku.variety,
                &sku.price.original_price,
                &sku.price.sale_price,
                &sku.price.is_special,
                &sku.price.save_percentage,
                &sku.price.promotion_start_date,
                &sku.price.promotion_end_date,
                &sku.size.cup_price,
                &sku.size.cup_measure,
                &sku.size.package_type,
                &sku.size.volume_size,
                &sku.quantity.unit,
                &sku.quantity.min,
                &sku.quantity.max,
                &sku.quantity.increment,
                &sku.quantity.supports_both_each_and_kg,
                &sku.quantity.average_weight_per_unit,
                &sku.availability_status,
                &sku.stock_level,
                &images,
                &allergens,
                &ingredients,
            ],
        )
        .await
        .map_err(|e| format!("Couldn't save SKU: {e}"))?;

    get(client, row.get(0)).await
}

pub async fn delete(client: &Client, id: i64) -> Result<(), String> {
    let changed = client
        .execute("DELETE FROM skus WHERE id = $1", &[&id])
        .await
        .map_err(|e| format!("Couldn't delete SKU {id}: {e}"))?;
    if changed == 0 {
        return Err(format!("No SKU with id {id}"));
    }
    Ok(())
}

/// Sets (or clears) this SKU as its item's preferred one. Setting it
/// first clears any other SKU already preferred for the same item.
pub async fn set_preferred(client: &Client, id: i64, is_preferred: bool) -> Result<StoredSku, String> {
    if is_preferred {
        let item_id: i64 = client
            .query_opt("SELECT item_id FROM skus WHERE id = $1", &[&id])
            .await
            .map_err(|e| format!("Couldn't find SKU {id}: {e}"))?
            .ok_or_else(|| format!("No SKU with id {id}"))?
            .get(0);
        client
            .execute(
                "UPDATE skus SET is_preferred = false WHERE item_id = $1 AND id != $2",
                &[&item_id, &id],
            )
            .await
            .map_err(|e| format!("Couldn't clear other preferred SKUs for item {item_id}: {e}"))?;
    }
    client
        .execute("UPDATE skus SET is_preferred = $1 WHERE id = $2", &[&is_preferred, &id])
        .await
        .map_err(|e| format!("Couldn't update SKU {id}: {e}"))?;
    get(client, id).await
}

pub async fn list_for_item(client: &Client, item_id: i64) -> Result<Vec<StoredSku>, String> {
    let rows = client
        .query(
            &format!("SELECT {SELECT_COLUMNS} FROM skus WHERE item_id = $1 ORDER BY created_at ASC"),
            &[&item_id],
        )
        .await
        .map_err(|e| format!("Couldn't list SKUs for item {item_id}: {e}"))?;
    Ok(rows.iter().map(row_to_sku).collect())
}
