use serde::{Deserialize, Serialize};

/// Only real, shopping-relevant units land on a list — the nominal
/// tsp/tbsp `recipe_items` can carry never reach here (see `recipe_items`).
pub const VALID_UNITS: &[&str] = &["g", "mL", "count"];

#[derive(Serialize, Deserialize, Clone, Debug)]
pub struct SkuSummary {
    pub id: i64,
    pub name: String,
    pub sale_price: Option<f64>,
    pub cup_price: Option<f64>,
    pub cup_measure: Option<String>,
}

#[derive(Serialize, Deserialize, Clone, Debug)]
pub struct ShoppingListLine {
    pub id: i64,
    pub item_id: i64,
    pub item_name: String,
    pub amount: Option<f64>,
    pub unit: Option<String>,
    /// The chosen SKU to buy — auto-picked cheapest (by cup_price) when
    /// the line's created, swappable after. `None` if the item has no
    /// linked SKUs yet — flagged, not guessed.
    pub sku: Option<SkuSummary>,
    /// Which recipe this line came from, if any and if still
    /// unambiguous — see `db::shopping_list_items::add_item`'s merge
    /// rule. Lets the UI re-group a recipe's lines under one card after
    /// reopening the list, instead of only within the session that added
    /// them.
    pub source_recipe_id: Option<i64>,
}

#[derive(Serialize, Deserialize, Clone, Debug)]
pub struct OmittedIngredient {
    pub recipe_id: i64,
    pub recipe_name: String,
    pub item_id: i64,
    pub item_name: String,
    pub amount: Option<f64>,
    pub unit: Option<String>,
}

#[derive(Serialize, Deserialize, Clone, Debug)]
pub struct OmittedPerishable {
    pub item_id: i64,
    pub item_name: String,
}

#[derive(Serialize, Deserialize, Clone, Debug)]
pub struct OmissionReport {
    pub recipe_ingredients: Vec<OmittedIngredient>,
    pub perishables: Vec<OmittedPerishable>,
}
