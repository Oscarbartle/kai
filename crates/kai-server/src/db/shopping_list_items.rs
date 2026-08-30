//! Postgres port of `src-tauri/src/db/shopping_list_items.rs` — the one
//! module with real cross-module logic (recipe expansion, cheapest-SKU
//! resolution, the omission report), not just flat CRUD. Ported rule for
//! rule from the SQLite side; see CLAUDE.md's Phase B notes for the
//! specific dialect swaps (`IS ?` → `IS NOT DISTINCT FROM $n` for
//! NULL-safe equality, since Postgres's plain `=` returns NULL rather
//! than matching two NULLs the way SQLite's `IS` does).

use crate::db::{items, recipe_items, recipes};
use deadpool_postgres::Client;
pub use kai_shared::shopping_list_items::VALID_UNITS;
use kai_shared::shopping_list_items::{
    OmissionReport, OmittedIngredient, OmittedPerishable, ShoppingListLine, SkuSummary,
};
use std::collections::HashSet;

const SELECT_LINE: &str = "
    SELECT
        sli.id, sli.item_id, items.name, sli.amount, sli.unit,
        skus.id, skus.name, skus.sale_price, skus.cup_price, skus.cup_measure,
        sli.source_recipe_id
    FROM shopping_list_items sli
    JOIN items ON items.id = sli.item_id
    LEFT JOIN skus ON skus.id = sli.sku_id
";

fn row_to_line(row: &tokio_postgres::Row) -> ShoppingListLine {
    let sku_id: Option<i64> = row.get(5);
    let sku = sku_id.map(|id| SkuSummary {
        id,
        name: row.get(6),
        sale_price: row.get(7),
        cup_price: row.get(8),
        cup_measure: row.get(9),
    });
    ShoppingListLine {
        id: row.get(0),
        item_id: row.get(1),
        item_name: row.get(2),
        amount: row.get(3),
        unit: row.get(4),
        sku,
        source_recipe_id: row.get(10),
    }
}

async fn get(client: &Client, id: i64) -> Result<ShoppingListLine, String> {
    let row = client
        .query_opt(&format!("{SELECT_LINE} WHERE sli.id = $1"), &[&id])
        .await
        .map_err(|e| format!("Couldn't load shopping list line {id}: {e}"))?
        .ok_or_else(|| format!("No shopping list line with id {id}"))?;
    Ok(row_to_line(&row))
}

fn validate_unit(unit: Option<&str>) -> Result<(), String> {
    match unit {
        None => Ok(()),
        Some(u) if VALID_UNITS.contains(&u) => Ok(()),
        Some(u) => Err(format!(
            "'{u}' isn't a shopping-list unit — use one of {VALID_UNITS:?}"
        )),
    }
}

/// The SKU to auto-pick for this item — a user-marked preferred SKU
/// first, unconditionally, else the cheapest linked SKU (by total cost,
/// or by cup_price if the item's own `cheapest_by` says "unit").
pub async fn cheapest_sku_id(client: &Client, item_id: i64) -> Result<Option<i64>, String> {
    let preferred = client
        .query_opt(
            "SELECT id FROM skus WHERE item_id = $1 AND is_preferred = true LIMIT 1",
            &[&item_id],
        )
        .await
        .map_err(|e| format!("Couldn't check for a preferred SKU for item {item_id}: {e}"))?;
    if let Some(row) = preferred {
        return Ok(Some(row.get(0)));
    }

    async fn by_total(client: &Client, item_id: i64) -> Result<Option<i64>, String> {
        Ok(client
            .query_opt(
                "SELECT id FROM skus WHERE item_id = $1 AND sale_price IS NOT NULL
                 ORDER BY sale_price ASC LIMIT 1",
                &[&item_id],
            )
            .await
            .map_err(|e| format!("Couldn't find cheapest SKU for item {item_id}: {e}"))?
            .map(|row| row.get(0)))
    }

    let item = items::get(client, item_id).await?;
    if item.cheapest_by != "unit" {
        return by_total(client, item_id).await;
    }

    let by_unit = client
        .query_opt(
            "SELECT id FROM skus WHERE item_id = $1 AND cup_price IS NOT NULL
             ORDER BY cup_price ASC LIMIT 1",
            &[&item_id],
        )
        .await
        .map_err(|e| format!("Couldn't find cheapest-by-unit SKU for item {item_id}: {e}"))?;
    if let Some(row) = by_unit {
        return Ok(Some(row.get(0)));
    }
    by_total(client, item_id).await
}

/// Adds an item to the list, or merges into an existing line for the
/// same item + unit + source if one's already there (summing amounts).
/// Scoped by `source_recipe_id` too, not just item + unit — see the
/// SQLite side's doc comment for the bug this avoids.
pub async fn add_item(
    client: &Client,
    list_id: i64,
    item_id: i64,
    amount: Option<f64>,
    unit: Option<&str>,
    source_recipe_id: Option<i64>,
) -> Result<ShoppingListLine, String> {
    validate_unit(unit)?;

    let existing = client
        .query_opt(
            "SELECT id FROM shopping_list_items
             WHERE list_id = $1 AND item_id = $2
               AND unit IS NOT DISTINCT FROM $3
               AND source_recipe_id IS NOT DISTINCT FROM $4",
            &[&list_id, &item_id, &unit, &source_recipe_id],
        )
        .await
        .map_err(|e| format!("Couldn't check for an existing line: {e}"))?;

    if let Some(row) = existing {
        let line_id: i64 = row.get(0);
        if let Some(add_amount) = amount {
            client
                .execute(
                    "UPDATE shopping_list_items SET amount = COALESCE(amount, 0) + $1 WHERE id = $2",
                    &[&add_amount, &line_id],
                )
                .await
                .map_err(|e| format!("Couldn't update line {line_id}: {e}"))?;
        }
        return get(client, line_id).await;
    }

    let sku_id = cheapest_sku_id(client, item_id).await?;
    let row = client
        .query_one(
            "INSERT INTO shopping_list_items (list_id, item_id, amount, unit, sku_id, source_recipe_id)
             VALUES ($1, $2, $3, $4, $5, $6) RETURNING id",
            &[&list_id, &item_id, &amount, &unit, &sku_id, &source_recipe_id],
        )
        .await
        .map_err(|e| format!("Couldn't add item {item_id} to list {list_id}: {e}"))?;
    get(client, row.get(0)).await
}

/// Expands a recipe's ingredients onto the list at a given scale.
/// Skipped: nominal units (tsp/tbsp), ingredients with no amount set,
/// and non-perishable ingredients — same three rules as the SQLite side.
async fn expand_recipe(
    client: &Client,
    list_id: i64,
    recipe_id: i64,
    scale: f64,
) -> Result<Vec<ShoppingListLine>, String> {
    let ingredients = recipe_items::list_for_recipe(client, recipe_id).await?;
    let mut lines = Vec::new();
    for ingredient in ingredients {
        let (Some(amount), Some(unit)) = (ingredient.amount, ingredient.unit.as_deref()) else {
            continue;
        };
        if !VALID_UNITS.contains(&unit) {
            continue; // tsp/tbsp — nominal, never hits the shopping list
        }
        if !items::get(client, ingredient.item_id).await?.is_perishable {
            continue;
        }
        lines.push(
            add_item(
                client,
                list_id,
                ingredient.item_id,
                Some(amount * scale),
                Some(unit),
                Some(recipe_id),
            )
            .await?,
        );
    }
    Ok(lines)
}

/// Expands a recipe's ingredients onto the list, scaled to
/// `target_servings` (falling back to the recipe's own `servings`, or
/// 1:1 if neither is set).
pub async fn add_recipe(
    client: &Client,
    list_id: i64,
    recipe_id: i64,
    target_servings: Option<i64>,
) -> Result<Vec<ShoppingListLine>, String> {
    let recipe = recipes::get(client, recipe_id).await?;
    let scale = match (target_servings, recipe.servings) {
        (Some(target), Some(base)) if base > 0 => target as f64 / base as f64,
        _ => 1.0,
    };
    expand_recipe(client, list_id, recipe_id, scale).await
}

/// Replaces however many times this recipe is currently on the list with
/// a fresh expansion at exactly `quantity` batches.
pub async fn set_recipe_quantity(
    client: &Client,
    list_id: i64,
    recipe_id: i64,
    quantity: f64,
) -> Result<Vec<ShoppingListLine>, String> {
    client
        .execute(
            "DELETE FROM shopping_list_items WHERE list_id = $1 AND source_recipe_id = $2",
            &[&list_id, &recipe_id],
        )
        .await
        .map_err(|e| format!("Couldn't clear recipe {recipe_id}'s existing lines: {e}"))?;
    expand_recipe(client, list_id, recipe_id, quantity).await
}

/// Sets (not adds to) a line's amount/unit directly.
pub async fn set_amount(
    client: &Client,
    line_id: i64,
    amount: Option<f64>,
    unit: Option<&str>,
) -> Result<ShoppingListLine, String> {
    validate_unit(unit)?;
    client
        .execute(
            "UPDATE shopping_list_items SET amount = $1, unit = $2 WHERE id = $3",
            &[&amount, &unit, &line_id],
        )
        .await
        .map_err(|e| format!("Couldn't set amount for line {line_id}: {e}"))?;
    get(client, line_id).await
}

/// Swaps the chosen SKU for a line — must belong to the same item.
/// `None` clears it back to "no SKU chosen".
pub async fn set_sku(client: &Client, line_id: i64, sku_id: Option<i64>) -> Result<ShoppingListLine, String> {
    if let Some(sid) = sku_id {
        let line = get(client, line_id).await?;
        let sku_item_id: i64 = client
            .query_opt("SELECT item_id FROM skus WHERE id = $1", &[&sid])
            .await
            .map_err(|e| format!("Couldn't find SKU {sid}: {e}"))?
            .ok_or_else(|| format!("No SKU with id {sid}"))?
            .get(0);
        if sku_item_id != line.item_id {
            return Err("That SKU doesn't belong to this line's item".into());
        }
    }
    client
        .execute(
            "UPDATE shopping_list_items SET sku_id = $1 WHERE id = $2",
            &[&sku_id, &line_id],
        )
        .await
        .map_err(|e| format!("Couldn't set SKU for line {line_id}: {e}"))?;
    get(client, line_id).await
}

pub async fn remove(client: &Client, line_id: i64) -> Result<(), String> {
    let changed = client
        .execute("DELETE FROM shopping_list_items WHERE id = $1", &[&line_id])
        .await
        .map_err(|e| format!("Couldn't remove line {line_id}: {e}"))?;
    if changed == 0 {
        return Err(format!("No shopping list line with id {line_id}"));
    }
    Ok(())
}

pub async fn list_for_list(client: &Client, list_id: i64) -> Result<Vec<ShoppingListLine>, String> {
    let rows = client
        .query(
            &format!("{SELECT_LINE} WHERE sli.list_id = $1 ORDER BY sli.id ASC"),
            &[&list_id],
        )
        .await
        .map_err(|e| format!("Couldn't list lines for list {list_id}: {e}"))?;
    Ok(rows.iter().map(row_to_line).collect())
}

/// What's missing from the given list(s) before they go to checkout —
/// see the SQLite side's doc comment for the full rationale (unchanged
/// here): recipe ingredients skipped for any reason, plus recipe-linked
/// perishables not already flagged or on the list.
pub async fn list_omitted(client: &Client, list_ids: &[i64]) -> Result<OmissionReport, String> {
    let mut lines = Vec::new();
    for &list_id in list_ids {
        lines.extend(list_for_list(client, list_id).await?);
    }
    let on_list: HashSet<i64> = lines.iter().map(|l| l.item_id).collect();
    let recipe_ids: HashSet<i64> = lines.iter().filter_map(|l| l.source_recipe_id).collect();

    let mut recipe_ingredients = Vec::new();
    let mut flagged_items: HashSet<i64> = HashSet::new();
    for recipe_id in recipe_ids {
        let recipe = recipes::get(client, recipe_id).await?;
        for ingredient in recipe_items::list_for_recipe(client, recipe_id).await? {
            if on_list.contains(&ingredient.item_id) {
                continue;
            }
            flagged_items.insert(ingredient.item_id);
            recipe_ingredients.push(OmittedIngredient {
                recipe_id,
                recipe_name: recipe.name.clone(),
                item_id: ingredient.item_id,
                item_name: ingredient.name,
                amount: ingredient.amount,
                unit: ingredient.unit,
            });
        }
    }

    // A plain `SELECT DISTINCT ... ORDER BY LOWER(name)` is rejected by
    // Postgres — unlike SQLite, it requires ORDER BY expressions to
    // appear in the select list for a DISTINCT query (confirmed live:
    // this failed against a real Postgres instance during Stage 3
    // testing). Wrapping the DISTINCT in a subquery sidesteps the
    // restriction since the outer SELECT isn't itself DISTINCT.
    let rows = client
        .query(
            "SELECT id, name FROM (
                SELECT DISTINCT items.id, items.name
                FROM items
                JOIN recipe_items ON recipe_items.item_id = items.id
                WHERE items.is_perishable = true
            ) AS recipe_linked_perishables
            ORDER BY LOWER(name)",
            &[],
        )
        .await
        .map_err(|e| format!("Couldn't list recipe-linked perishables: {e}"))?;

    let mut perishables = Vec::new();
    for row in rows {
        let item_id: i64 = row.get(0);
        let item_name: String = row.get(1);
        if on_list.contains(&item_id) || flagged_items.contains(&item_id) {
            continue;
        }
        perishables.push(OmittedPerishable { item_id, item_name });
    }

    Ok(OmissionReport { recipe_ingredients, perishables })
}
