use serde::{Deserialize, Serialize};

/// `g`/`mL`/`count` are real, shopping-relevant amounts — they're what a
/// future shopping-list pass will actually convert against a SKU's own
/// pack size/`quantity` data (`count` for "3 onions"-style discrete
/// amounts, matched against an "Each"-purchased SKU). `tsp`/`tbsp` are
/// nominal: kept for cooking reference on the recipe, deliberately never
/// fed into that math. No cup, no arbitrary units — see CLAUDE.md for
/// why this set is narrow on purpose.
pub const VALID_UNITS: &[&str] = &["g", "mL", "count", "tsp", "tbsp"];

#[derive(Serialize, Deserialize, Clone, Debug)]
pub struct RecipeIngredient {
    pub item_id: i64,
    pub name: String,
    pub amount: Option<f64>,
    pub unit: Option<String>,
}
