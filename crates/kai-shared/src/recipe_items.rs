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
    /// A SKU of this item pinned for this recipe: lines added from the
    /// recipe use it, trumping the item's ★ preferred SKU and the
    /// cheapest-pick. `None` = no pin. The pin goes (back to `None`) if the
    /// SKU is deleted. `#[serde(default)]` keeps a newer desktop working
    /// against a server from before the field existed.
    #[serde(default)]
    pub sku_id: Option<i64>,
}
