use crate::woolworths::{Sku, SkuPrice, SkuQuantity, SkuSize};
use rusqlite::{params, Connection};
use serde::Serialize;

#[derive(Serialize, Clone, Debug)]
pub struct StoredSku {
    pub id: i64,
    pub item_id: i64,
    /// Trumps `items.cheapest_by` entirely when set — see
    /// `shopping_list_items::cheapest_sku_id`. At most one SKU per item
    /// can be preferred at a time (see `set_preferred`).
    pub is_preferred: bool,
    #[serde(flatten)]
    pub sku: Sku,
}

/// Persists a fetched `Sku` against an item. Re-saving the same
/// provider+sku pair for the same item updates the cached fields
/// (price, stock, etc.) instead of creating a duplicate row.
pub fn save(conn: &Connection, item_id: i64, sku: &Sku) -> Result<StoredSku, String> {
    let images = serde_json::to_string(&sku.images).map_err(|e| e.to_string())?;
    let allergens = serde_json::to_string(&sku.allergens).map_err(|e| e.to_string())?;
    let ingredients = serde_json::to_string(&sku.ingredients).map_err(|e| e.to_string())?;

    conn.execute(
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
            ?1, ?2, ?3, ?4, ?5, ?6,
            ?7, ?8, ?9, ?10,
            ?11, ?12,
            ?13, ?14, ?15, ?16,
            ?17, ?18, ?19, ?20,
            ?21, ?22,
            ?23, ?24, ?25, ?26, ?27,
            datetime('now')
        )
        ON CONFLICT(item_id, provider, sku) DO UPDATE SET
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
            updated_at = datetime('now')",
        params![
            item_id,
            sku.provider,
            sku.sku,
            sku.name,
            sku.brand,
            sku.variety,
            sku.price.original_price,
            sku.price.sale_price,
            sku.price.is_special,
            sku.price.save_percentage,
            sku.price.promotion_start_date,
            sku.price.promotion_end_date,
            sku.size.cup_price,
            sku.size.cup_measure,
            sku.size.package_type,
            sku.size.volume_size,
            sku.quantity.unit,
            sku.quantity.min,
            sku.quantity.max,
            sku.quantity.increment,
            sku.quantity.supports_both_each_and_kg,
            sku.quantity.average_weight_per_unit,
            sku.availability_status,
            sku.stock_level,
            images,
            allergens,
            ingredients,
        ],
    )
    .map_err(|e| format!("Couldn't save SKU: {e}"))?;

    conn.query_row(
        "SELECT id FROM skus WHERE item_id = ?1 AND provider = ?2 AND sku = ?3",
        params![item_id, sku.provider, sku.sku],
        |row| row.get::<_, i64>(0),
    )
    .map_err(|e| format!("Couldn't find saved SKU: {e}"))
    .and_then(|id| get(conn, id))
}

pub fn delete(conn: &Connection, id: i64) -> Result<(), String> {
    let changed = conn
        .execute("DELETE FROM skus WHERE id = ?1", params![id])
        .map_err(|e| format!("Couldn't delete SKU {id}: {e}"))?;
    if changed == 0 {
        return Err(format!("No SKU with id {id}"));
    }
    Ok(())
}

/// Sets (or clears) this SKU as its item's preferred one. Setting it
/// first clears any other SKU already preferred for the same item —
/// only one can be preferred at a time, since "always add this one by
/// default" only makes sense as a single choice.
pub fn set_preferred(conn: &Connection, id: i64, is_preferred: bool) -> Result<StoredSku, String> {
    if is_preferred {
        let item_id: i64 = conn
            .query_row("SELECT item_id FROM skus WHERE id = ?1", params![id], |row| {
                row.get(0)
            })
            .map_err(|e| format!("Couldn't find SKU {id}: {e}"))?;
        conn.execute(
            "UPDATE skus SET is_preferred = 0 WHERE item_id = ?1 AND id != ?2",
            params![item_id, id],
        )
        .map_err(|e| format!("Couldn't clear other preferred SKUs for item {item_id}: {e}"))?;
    }
    conn.execute(
        "UPDATE skus SET is_preferred = ?1 WHERE id = ?2",
        params![is_preferred, id],
    )
    .map_err(|e| format!("Couldn't update SKU {id}: {e}"))?;
    get(conn, id)
}

pub fn list_for_item(conn: &Connection, item_id: i64) -> Result<Vec<StoredSku>, String> {
    let mut stmt = conn
        .prepare("SELECT id FROM skus WHERE item_id = ?1 ORDER BY created_at ASC")
        .map_err(|e| format!("Couldn't prepare SKU list query: {e}"))?;

    let ids = stmt
        .query_map(params![item_id], |row| row.get::<_, i64>(0))
        .map_err(|e| format!("Couldn't list SKUs: {e}"))?
        .collect::<Result<Vec<_>, _>>()
        .map_err(|e| format!("Couldn't read SKU rows: {e}"))?;

    ids.into_iter().map(|id| get(conn, id)).collect()
}

pub fn get(conn: &Connection, id: i64) -> Result<StoredSku, String> {
    conn.query_row(
        "SELECT
            id, item_id, provider, sku, name, brand, variety,
            original_price, sale_price, is_special, save_percentage,
            promotion_start_date, promotion_end_date,
            cup_price, cup_measure, package_type, volume_size,
            unit, quantity_min, quantity_max, quantity_increment,
            supports_both_units, average_weight_per_unit,
            availability_status, stock_level, images, allergens, ingredients,
            is_preferred
        FROM skus WHERE id = ?1",
        params![id],
        |row| {
            let images: String = row.get(25)?;
            let allergens: String = row.get(26)?;
            let ingredients: String = row.get(27)?;

            Ok(StoredSku {
                id: row.get(0)?,
                item_id: row.get(1)?,
                is_preferred: row.get(28)?,
                sku: Sku {
                    provider: row.get(2)?,
                    sku: row.get(3)?,
                    name: row.get(4)?,
                    brand: row.get(5)?,
                    variety: row.get(6)?,
                    price: SkuPrice {
                        original_price: row.get(7)?,
                        sale_price: row.get(8)?,
                        is_special: row.get(9)?,
                        save_percentage: row.get(10)?,
                        promotion_start_date: row.get(11)?,
                        promotion_end_date: row.get(12)?,
                    },
                    size: SkuSize {
                        cup_price: row.get(13)?,
                        cup_measure: row.get(14)?,
                        package_type: row.get(15)?,
                        volume_size: row.get(16)?,
                    },
                    quantity: SkuQuantity {
                        unit: row.get(17)?,
                        min: row.get(18)?,
                        max: row.get(19)?,
                        increment: row.get(20)?,
                        supports_both_each_and_kg: row.get(21)?,
                        average_weight_per_unit: row.get(22)?,
                    },
                    availability_status: row.get(23)?,
                    stock_level: row.get(24)?,
                    images: serde_json::from_str(&images).unwrap_or_default(),
                    allergens: serde_json::from_str(&allergens).unwrap_or_default(),
                    ingredients: serde_json::from_str(&ingredients).unwrap_or_default(),
                },
            })
        },
    )
    .map_err(|e| format!("Couldn't load SKU {id}: {e}"))
}
