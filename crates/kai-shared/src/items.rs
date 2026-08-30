use serde::{Deserialize, Serialize};

/// Which metric the shopping-list auto-pick compares this item's linked
/// SKUs by — see `shopping_list_items::cheapest_sku_id`. Validated in
/// Rust, not a DB constraint, same pattern as `recipe_items::VALID_UNITS`.
pub const VALID_CHEAPEST_BY: &[&str] = &["total", "unit"];

#[derive(Serialize, Deserialize, Clone, Debug)]
pub struct Item {
    pub id: i64,
    pub name: String,
    pub is_perishable: bool,
    pub image_url: Option<String>,
    pub cheapest_by: String,
    pub created_at: String,
}
