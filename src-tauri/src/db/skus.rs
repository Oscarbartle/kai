use crate::woolworths::{Sku, SkuPrice, SkuQuantity, SkuSize};
use rusqlite::{params, Connection};

// StoredSku moved to kai-shared (Phase B) — see crates/kai-shared/src/skus.rs.
pub use kai_shared::skus::{PricePoint, StoredSku};

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

    let id = conn
        .query_row(
            "SELECT id FROM skus WHERE item_id = ?1 AND provider = ?2 AND sku = ?3",
            params![item_id, sku.provider, sku.sku],
            |row| row.get::<_, i64>(0),
        )
        .map_err(|e| format!("Couldn't find saved SKU: {e}"))?;

    // Every save is a fresh look at the price, so every save is a dot.
    conn.execute(
        "INSERT INTO sku_price_history (sku_id, sale_price, original_price, is_special, cup_price)
         VALUES (?1, ?2, ?3, ?4, ?5)",
        params![
            id,
            sku.price.sale_price,
            sku.price.original_price,
            sku.price.is_special,
            sku.size.cup_price,
        ],
    )
    .map_err(|e| format!("Couldn't record price history: {e}"))?;

    get(conn, id)
}

/// Every recorded price for every SKU of an item, oldest first.
pub fn price_history_for_item(conn: &Connection, item_id: i64) -> Result<Vec<PricePoint>, String> {
    let mut stmt = conn
        .prepare(
            "SELECT h.sku_id, strftime('%Y-%m-%dT%H:%M:%SZ', h.recorded_at),
                    h.sale_price, h.original_price, h.is_special, h.cup_price
             FROM sku_price_history h
             JOIN skus s ON s.id = h.sku_id
             WHERE s.item_id = ?1
             ORDER BY h.recorded_at ASC, h.id ASC",
        )
        .map_err(|e| format!("Couldn't prepare price history query: {e}"))?;
    let rows = stmt
        .query_map(params![item_id], |row| {
            Ok(PricePoint {
                sku_id: row.get(0)?,
                recorded_at: row.get(1)?,
                sale_price: row.get(2)?,
                original_price: row.get(3)?,
                is_special: row.get(4)?,
                cup_price: row.get(5)?,
            })
        })
        .map_err(|e| format!("Couldn't load price history for item {item_id}: {e}"))?;
    rows.collect::<Result<Vec<_>, _>>()
        .map_err(|e| format!("Couldn't read price history: {e}"))
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
            is_preferred,
            strftime('%Y-%m-%dT%H:%M:%SZ', updated_at)
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
                updated_at: row.get::<_, Option<String>>(29)?.unwrap_or_default(),
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

#[cfg(test)]
mod tests {
    use super::*;
    use crate::db::items;

    fn sku() -> Sku {
        Sku {
            provider: "woolworths".into(),
            sku: "144329".into(),
            name: "onions".into(),
            brand: None,
            variety: None,
            price: SkuPrice::default(),
            size: SkuSize::default(),
            quantity: SkuQuantity {
                unit: "Each".into(),
                ..Default::default()
            },
            availability_status: None,
            stock_level: None,
            images: vec![],
            allergens: vec![],
            ingredients: vec![],
        }
    }

    fn conn() -> Connection {
        let mut conn = Connection::open_in_memory().unwrap();
        conn.pragma_update(None, "foreign_keys", true).unwrap();
        crate::db::migrations().to_latest(&mut conn).unwrap();
        conn
    }

    fn priced(sale: f64, special: bool) -> Sku {
        let mut s = sku();
        s.price.sale_price = Some(sale);
        s.price.original_price = Some(if special { sale + 1.0 } else { sale });
        s.price.is_special = special;
        s.size.cup_price = Some(sale * 2.0);
        s
    }

    #[test]
    fn every_save_adds_a_price_point_oldest_first() {
        let conn = conn();
        let item = items::create(&conn, "Onion").unwrap();
        let stored = save(&conn, item.id, &priced(3.50, false)).unwrap();
        // A refresh with an unchanged price is still a dot, and so is a special.
        save(&conn, item.id, &priced(3.50, false)).unwrap();
        save(&conn, item.id, &priced(2.80, true)).unwrap();
        // Make the order depend on the date, not on insertion luck.
        conn.execute(
            "UPDATE sku_price_history SET recorded_at = '2026-01-01 00:00:00' WHERE id = 3",
            [],
        )
        .unwrap();

        let history = price_history_for_item(&conn, item.id).unwrap();
        assert_eq!(history.len(), 3);
        assert_eq!(history[0].recorded_at, "2026-01-01T00:00:00Z");
        assert_eq!(history[0].sale_price, Some(2.80));
        assert!(history[0].is_special);
        assert_eq!(history[0].original_price, Some(3.80));
        assert_eq!(history[0].cup_price, Some(5.60));
        assert!(history.iter().all(|p| p.sku_id == stored.id));
        assert!(history[1].recorded_at.ends_with('Z') && history[1].recorded_at.starts_with("20"));
    }

    #[test]
    fn price_history_is_per_item_and_goes_with_its_sku() {
        let conn = conn();
        let onion = items::create(&conn, "Onion").unwrap();
        let milk = items::create(&conn, "Milk").unwrap();
        let a = save(&conn, onion.id, &priced(3.0, false)).unwrap();
        let mut other = priced(4.0, false);
        other.sku = "999".into();
        let b = save(&conn, onion.id, &other).unwrap();
        save(&conn, milk.id, &priced(5.0, false)).unwrap();

        let h = price_history_for_item(&conn, onion.id).unwrap();
        assert_eq!(h.len(), 2, "both of the onion's SKUs, none of the milk's");
        assert!(h.iter().any(|p| p.sku_id == a.id) && h.iter().any(|p| p.sku_id == b.id));

        delete(&conn, a.id).unwrap();
        let h = price_history_for_item(&conn, onion.id).unwrap();
        assert_eq!(h.len(), 1, "deleting a SKU deletes its history");
        assert_eq!(h[0].sku_id, b.id);
        assert!(price_history_for_item(&conn, 12345).unwrap().is_empty());
    }

    #[test]
    fn migration_seeds_one_point_per_existing_sku_from_its_last_fetch() {
        let mut conn = Connection::open_in_memory().unwrap();
        conn.pragma_update(None, "foreign_keys", true).unwrap();
        // The database as it was before price history existed: every
        // migration except the last one (the one that adds the table).
        crate::db::migrations().to_version(&mut conn, 22).unwrap();
        conn.execute("INSERT INTO items (name) VALUES ('Onion')", []).unwrap();
        conn.execute(
            "INSERT INTO skus (item_id, provider, sku, name, sale_price, original_price, is_special, cup_price, unit, updated_at)
             VALUES (1, 'woolworths', '1', 'onions', 3.5, 3.5, 0, 7.0, 'Each', '2026-02-03 04:05:06')",
            [],
        )
        .unwrap();
        crate::db::migrations().to_latest(&mut conn).unwrap();
        let h = price_history_for_item(&conn, 1).unwrap();
        assert_eq!(h.len(), 1);
        assert_eq!(h[0].recorded_at, "2026-02-03T04:05:06Z", "dated by the last fetch, not by migration day");
        assert_eq!((h[0].sale_price, h[0].cup_price), (Some(3.5), Some(7.0)));
    }

    #[test]
    fn updated_at_is_when_it_was_fetched_and_starring_does_not_touch_it() {
        let conn = conn();
        let item = items::create(&conn, "Onion").unwrap();

        let stored = save(&conn, item.id, &sku()).unwrap();
        // RFC 3339 in UTC, so the apps can parse it without guessing a zone.
        assert!(stored.updated_at.ends_with('Z') && stored.updated_at.contains('T'), "{}", stored.updated_at);
        assert!(stored.updated_at.starts_with("20"));

        // Pretend it was fetched long ago.
        conn.execute(
            "UPDATE skus SET updated_at = '2020-01-02 03:04:05' WHERE id = ?1",
            params![stored.id],
        )
        .unwrap();
        assert_eq!(get(&conn, stored.id).unwrap().updated_at, "2020-01-02T03:04:05Z");

        // Starring a SKU is not a price check: the age must not reset.
        set_preferred(&conn, stored.id, true).unwrap();
        assert_eq!(get(&conn, stored.id).unwrap().updated_at, "2020-01-02T03:04:05Z");

        // A refresh (a save of the same SKU again) does reset it.
        save(&conn, item.id, &sku()).unwrap();
        assert_ne!(get(&conn, stored.id).unwrap().updated_at, "2020-01-02T03:04:05Z");
    }
}

