use crate::db::{items, recipe_items, recipes};
use rusqlite::{params, Connection, OptionalExtension};

// SkuSummary/ShoppingListLine/OmissionReport family moved to kai-shared
// (Phase B) — see crates/kai-shared/src/shopping_list_items.rs.
pub use kai_shared::shopping_list_items::{
    OmissionReport, OmittedIngredient, OmittedPerishable, ShoppingListLine, SkuSummary, VALID_UNITS,
};

const SELECT_LINE: &str = "
    SELECT
        sli.id, sli.item_id, items.name, sli.amount, sli.unit,
        skus.id, skus.name, skus.sale_price, skus.cup_price, skus.cup_measure,
        sli.source_recipe_id
    FROM shopping_list_items sli
    JOIN items ON items.id = sli.item_id
    LEFT JOIN skus ON skus.id = sli.sku_id
";

fn row_to_line(row: &rusqlite::Row) -> rusqlite::Result<ShoppingListLine> {
    let sku_id: Option<i64> = row.get(5)?;
    let sku = match sku_id {
        Some(id) => Some(SkuSummary {
            id,
            name: row.get(6)?,
            sale_price: row.get(7)?,
            cup_price: row.get(8)?,
            cup_measure: row.get(9)?,
        }),
        None => None,
    };
    Ok(ShoppingListLine {
        id: row.get(0)?,
        item_id: row.get(1)?,
        item_name: row.get(2)?,
        amount: row.get(3)?,
        unit: row.get(4)?,
        sku,
        source_recipe_id: row.get(10)?,
    })
}

fn get(conn: &Connection, id: i64) -> Result<ShoppingListLine, String> {
    conn.query_row(
        &format!("{SELECT_LINE} WHERE sli.id = ?1"),
        params![id],
        row_to_line,
    )
    .map_err(|e| format!("Couldn't load shopping list line {id}: {e}"))
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
/// (the star on the SKU widget) if there is one, trumping everything
/// else unconditionally. Otherwise the cheapest linked SKU: by plain
/// total cost (`sale_price`, what you'd actually pay) unless the item's
/// own `cheapest_by` says `"unit"`, in which case it compares by
/// `cup_price` ($/kg or $/L) instead, the better metric when
/// per-pack-size comparison is what actually matters for that
/// particular item. Per-item, not global — a reasonable default doesn't
/// fit every item (see `items::VALID_CHEAPEST_BY`). Falls back to
/// `sale_price` if the "unit" item has no SKU with a `cup_price` set.
/// `None` if the item has no linked SKUs at all.
pub fn cheapest_sku_id(conn: &Connection, item_id: i64) -> Result<Option<i64>, String> {
    let preferred: Option<i64> = conn
        .query_row(
            "SELECT id FROM skus WHERE item_id = ?1 AND is_preferred = 1 LIMIT 1",
            params![item_id],
            |row| row.get(0),
        )
        .optional()
        .map_err(|e| format!("Couldn't check for a preferred SKU for item {item_id}: {e}"))?;
    if preferred.is_some() {
        return Ok(preferred);
    }

    let by_total = || {
        conn.query_row(
            "SELECT id FROM skus WHERE item_id = ?1 AND sale_price IS NOT NULL
             ORDER BY sale_price ASC LIMIT 1",
            params![item_id],
            |row| row.get(0),
        )
        .optional()
        .map_err(|e| format!("Couldn't find cheapest SKU for item {item_id}: {e}"))
    };

    let item = items::get(conn, item_id)?;
    if item.cheapest_by != "unit" {
        return by_total();
    }

    let by_unit: Option<i64> = conn
        .query_row(
            "SELECT id FROM skus WHERE item_id = ?1 AND cup_price IS NOT NULL
             ORDER BY cup_price ASC LIMIT 1",
            params![item_id],
            |row| row.get(0),
        )
        .optional()
        .map_err(|e| format!("Couldn't find cheapest-by-unit SKU for item {item_id}: {e}"))?;
    if by_unit.is_some() {
        return Ok(by_unit);
    }
    by_total()
}

/// Adds an item to the list, or merges into an existing line for the
/// same item + unit + source if one's already there (summing amounts) —
/// so adding the same recipe twice doubles its own contribution onto
/// one line, not two. A mismatched unit, *or a different source*, for
/// an item already on the list becomes its own separate line rather
/// than something this has to reject, coerce, or merge across.
///
/// Scoping the merge by `source_recipe_id` too (not just item + unit)
/// matters: without it, a recipe's ingredient could silently merge into
/// an unrelated plain item-drop's line for the same item+unit, and a
/// previous version of this function then cleared that line's source
/// tag to avoid misattributing it — which broke `set_recipe_quantity`'s
/// "delete this recipe's current lines" step the moment it happened,
/// since the line was no longer tagged as this recipe's to find. Each
/// quantity change after that just summed on top again instead of
/// resetting — confirmed live (a recipe sharing an ingredient with a
/// separately-dropped item spiralled to needing 90 of it after a
/// handful of + clicks). Scoping the merge avoids the cross-source
/// merge in the first place, so there's nothing left to disambiguate.
pub fn add_item(
    conn: &Connection,
    list_id: i64,
    item_id: i64,
    amount: Option<f64>,
    unit: Option<&str>,
    source_recipe_id: Option<i64>,
) -> Result<ShoppingListLine, String> {
    validate_unit(unit)?;

    let existing_id: Option<i64> = conn
        .query_row(
            "SELECT id FROM shopping_list_items
             WHERE list_id = ?1 AND item_id = ?2 AND unit IS ?3 AND source_recipe_id IS ?4",
            params![list_id, item_id, unit, source_recipe_id],
            |row| row.get(0),
        )
        .optional()
        .map_err(|e| format!("Couldn't check for an existing line: {e}"))?;

    if let Some(line_id) = existing_id {
        if let Some(add_amount) = amount {
            conn.execute(
                "UPDATE shopping_list_items SET amount = COALESCE(amount, 0) + ?1 WHERE id = ?2",
                params![add_amount, line_id],
            )
            .map_err(|e| format!("Couldn't update line {line_id}: {e}"))?;
        }
        return get(conn, line_id);
    }

    let sku_id = cheapest_sku_id(conn, item_id)?;
    conn.execute(
        "INSERT INTO shopping_list_items (list_id, item_id, amount, unit, sku_id, source_recipe_id)
         VALUES (?1, ?2, ?3, ?4, ?5, ?6)",
        params![list_id, item_id, amount, unit, sku_id, source_recipe_id],
    )
    .map_err(|e| format!("Couldn't add item {item_id} to list {list_id}: {e}"))?;
    get(conn, conn.last_insert_rowid())
}

/// Expands a recipe's ingredients onto the list at a given scale.
/// Skipped, nothing meaningful/wanted to add for these: nominal units
/// (tsp/tbsp), ingredients with no amount set, and — new — non-perishable
/// ingredients (salt, spices, tinned goods, ...), since those usually
/// outlast a single shopping trip and auto-adding one every time a
/// recipe using it goes on a list would mean re-buying things you
/// almost certainly already have. `list_omitted` below is the safety
/// net for the case that's actually run out. Shared by `add_recipe`
/// (scale derived from servings) and `set_recipe_quantity` (scale is
/// the quantity itself) — those are genuinely different notions of
/// "scale" that happen to do the same expansion underneath.
fn expand_recipe(
    conn: &Connection,
    list_id: i64,
    recipe_id: i64,
    scale: f64,
) -> Result<Vec<ShoppingListLine>, String> {
    let ingredients = recipe_items::list_for_recipe(conn, recipe_id)?;
    let mut lines = Vec::new();
    for ingredient in ingredients {
        let (Some(amount), Some(unit)) = (ingredient.amount, ingredient.unit.as_deref()) else {
            continue;
        };
        if !VALID_UNITS.contains(&unit) {
            continue; // tsp/tbsp — nominal, never hits the shopping list
        }
        if !items::get(conn, ingredient.item_id)?.is_perishable {
            continue;
        }
        lines.push(add_item(
            conn,
            list_id,
            ingredient.item_id,
            Some(amount * scale),
            Some(unit),
            Some(recipe_id),
        )?);
    }
    Ok(lines)
}

/// Expands a recipe's ingredients onto the list, scaled to
/// `target_servings` (falling back to the recipe's own `servings`, or
/// 1:1 if neither is set).
pub fn add_recipe(
    conn: &Connection,
    list_id: i64,
    recipe_id: i64,
    target_servings: Option<i64>,
) -> Result<Vec<ShoppingListLine>, String> {
    let recipe = recipes::get(conn, recipe_id)?;
    let scale = match (target_servings, recipe.servings) {
        (Some(target), Some(base)) if base > 0 => target as f64 / base as f64,
        _ => 1.0,
    };
    expand_recipe(conn, list_id, recipe_id, scale)
}

/// Replaces however many times this recipe is currently on the list
/// with a fresh expansion at exactly `quantity` batches — used by the
/// widget's quantity stepper. Deliberately not servings-based like
/// `add_recipe`: "how many times is this recipe on the list" and
/// "scaled to feed how many people" are different questions, and the
/// servings one breaks entirely for a recipe with no `servings` set (its
/// scale is always 1 regardless of target — see `add_recipe` above).
/// Only removes lines this recipe unambiguously owns (`source_recipe_id`
/// still matches) — see `add_item`'s merge rule for how that can go
/// null.
pub fn set_recipe_quantity(
    conn: &Connection,
    list_id: i64,
    recipe_id: i64,
    quantity: f64,
) -> Result<Vec<ShoppingListLine>, String> {
    conn.execute(
        "DELETE FROM shopping_list_items WHERE list_id = ?1 AND source_recipe_id = ?2",
        params![list_id, recipe_id],
    )
    .map_err(|e| format!("Couldn't clear recipe {recipe_id}'s existing lines: {e}"))?;
    expand_recipe(conn, list_id, recipe_id, quantity)
}

/// Sets (not adds to) a line's amount/unit directly — used by the
/// quantity stepper on a dropped widget, which wants to land on an
/// exact number rather than accumulate via `add_item`'s merge-by-sum
/// behavior.
pub fn set_amount(
    conn: &Connection,
    line_id: i64,
    amount: Option<f64>,
    unit: Option<&str>,
) -> Result<ShoppingListLine, String> {
    validate_unit(unit)?;
    conn.execute(
        "UPDATE shopping_list_items SET amount = ?1, unit = ?2 WHERE id = ?3",
        params![amount, unit, line_id],
    )
    .map_err(|e| format!("Couldn't set amount for line {line_id}: {e}"))?;
    get(conn, line_id)
}

/// Swaps the chosen SKU for a line — must belong to the same item.
/// `None` clears it back to "no SKU chosen".
pub fn set_sku(conn: &Connection, line_id: i64, sku_id: Option<i64>) -> Result<ShoppingListLine, String> {
    if let Some(sid) = sku_id {
        let line = get(conn, line_id)?;
        let sku_item_id: i64 = conn
            .query_row("SELECT item_id FROM skus WHERE id = ?1", params![sid], |row| {
                row.get(0)
            })
            .map_err(|e| format!("Couldn't find SKU {sid}: {e}"))?;
        if sku_item_id != line.item_id {
            return Err("That SKU doesn't belong to this line's item".into());
        }
    }
    conn.execute(
        "UPDATE shopping_list_items SET sku_id = ?1 WHERE id = ?2",
        params![sku_id, line_id],
    )
    .map_err(|e| format!("Couldn't set SKU for line {line_id}: {e}"))?;
    get(conn, line_id)
}

pub fn remove(conn: &Connection, line_id: i64) -> Result<(), String> {
    let changed = conn
        .execute("DELETE FROM shopping_list_items WHERE id = ?1", params![line_id])
        .map_err(|e| format!("Couldn't remove line {line_id}: {e}"))?;
    if changed == 0 {
        return Err(format!("No shopping list line with id {line_id}"));
    }
    Ok(())
}

/// Empties a list's lines without deleting the list itself — the
/// "Clear list" button. Not an error if the list was already empty
/// (0 rows deleted is a perfectly fine outcome here, unlike `remove`
/// above where a missing line id is a real mistake to flag).
pub fn clear(conn: &Connection, list_id: i64) -> Result<(), String> {
    conn.execute("DELETE FROM shopping_list_items WHERE list_id = ?1", params![list_id])
        .map_err(|e| format!("Couldn't clear list {list_id}: {e}"))?;
    Ok(())
}

pub fn list_for_list(conn: &Connection, list_id: i64) -> Result<Vec<ShoppingListLine>, String> {
    let mut stmt = conn
        .prepare(&format!("{SELECT_LINE} WHERE sli.list_id = ?1 ORDER BY sli.id ASC"))
        .map_err(|e| format!("Couldn't prepare shopping list line query: {e}"))?;

    let rows = stmt
        .query_map(params![list_id], row_to_line)
        .map_err(|e| format!("Couldn't list lines for list {list_id}: {e}"))?;

    rows.collect::<Result<Vec<_>, _>>()
        .map_err(|e| format!("Couldn't read shopping list line rows: {e}"))
}

/// What's missing from the given list(s) before they go to checkout —
/// the reminder pass for `expand_recipe`'s auto-skips (nominal tsp/tbsp,
/// unset amounts, non-perishables) and for anything else that's just
/// not there (a line removed by hand, an item that never got added).
/// Two categories, not one:
///
/// - `recipe_ingredients`: for every recipe that actually has a line on
///   this list right now (i.e. you're shopping for it this trip), any
///   of its *other* ingredients that don't have a line here too —
///   whatever the reason. Scoped to recipes genuinely on the list, so
///   this doesn't fire for a recipe you're not even shopping for.
/// - `perishables`: perishable items linked to *any* recipe anywhere
///   (not just ones on this list) that aren't already flagged above and
///   aren't already on the list — the broader "you cook with this
///   regularly, did you just run out?" check. Items already surfaced in
///   `recipe_ingredients` are excluded here rather than shown twice.
pub fn list_omitted(conn: &Connection, list_ids: &[i64]) -> Result<OmissionReport, String> {
    let mut lines = Vec::new();
    for &list_id in list_ids {
        lines.extend(list_for_list(conn, list_id)?);
    }
    let on_list: std::collections::HashSet<i64> = lines.iter().map(|l| l.item_id).collect();
    let recipe_ids: std::collections::HashSet<i64> =
        lines.iter().filter_map(|l| l.source_recipe_id).collect();

    let mut recipe_ingredients = Vec::new();
    let mut flagged_items: std::collections::HashSet<i64> = std::collections::HashSet::new();
    for recipe_id in recipe_ids {
        let recipe = recipes::get(conn, recipe_id)?;
        for ingredient in recipe_items::list_for_recipe(conn, recipe_id)? {
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

    let mut stmt = conn
        .prepare(
            "SELECT DISTINCT items.id, items.name
             FROM items
             JOIN recipe_items ON recipe_items.item_id = items.id
             WHERE items.is_perishable = 1
             ORDER BY items.name COLLATE NOCASE",
        )
        .map_err(|e| format!("Couldn't prepare omitted-perishables query: {e}"))?;
    let rows = stmt
        .query_map([], |row| Ok((row.get::<_, i64>(0)?, row.get::<_, String>(1)?)))
        .map_err(|e| format!("Couldn't list recipe-linked perishables: {e}"))?;

    let mut perishables = Vec::new();
    for row in rows {
        let (item_id, item_name) = row.map_err(|e| format!("Couldn't read perishable row: {e}"))?;
        if on_list.contains(&item_id) || flagged_items.contains(&item_id) {
            continue;
        }
        perishables.push(OmittedPerishable { item_id, item_name });
    }

    Ok(OmissionReport { recipe_ingredients, perishables })
}
