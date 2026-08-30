use serde::{Deserialize, Serialize};

#[derive(Serialize, Deserialize, Clone, Debug, Default)]
pub struct SkuPrice {
    pub original_price: Option<f64>,
    pub sale_price: Option<f64>,
    pub is_special: bool,
    pub save_percentage: Option<f64>,
    /// ISO-ish timestamps ("2026-08-24T00:00:00"), straight from the API.
    /// Only populated when `is_special` is true.
    pub promotion_start_date: Option<String>,
    pub promotion_end_date: Option<String>,
}

#[derive(Serialize, Deserialize, Clone, Debug, Default)]
pub struct SkuSize {
    pub cup_price: Option<f64>,
    pub cup_measure: Option<String>,
    pub package_type: Option<String>,
    pub volume_size: Option<String>,
}

/// How this SKU is actually purchased. Woolworths' own `unit` field is
/// "Each" for discrete items or "Kg" for loose/weighed ones — confirmed
/// across produce, meat, seafood, and deli, no ambiguous cases found.
/// `min`/`increment` (kg if by weight, whole units if not) are what let
/// a recipe's needed quantity later get rounded to something actually
/// orderable, e.g. "300g of loose onions" -> 0.3kg (0.1kg increments).
///
/// Some SKUs (e.g. loose onions) support *both* modes — the site itself
/// offers a Weight/Quantity radio toggle at add-to-cart time. `unit` above
/// is just the default; `supports_both_each_and_kg` + `average_weight_per_unit`
/// (populated only when true) preserve that the other mode is available too,
/// with the conversion factor between them.
#[derive(Serialize, Deserialize, Clone, Debug, Default)]
pub struct SkuQuantity {
    pub unit: String,
    pub min: Option<f64>,
    pub max: Option<f64>,
    pub increment: Option<f64>,
    pub supports_both_each_and_kg: bool,
    pub average_weight_per_unit: Option<f64>,
}

#[derive(Serialize, Deserialize, Clone, Debug)]
pub struct Sku {
    pub provider: String,
    pub sku: String,
    pub name: String,
    pub brand: Option<String>,
    pub variety: Option<String>,
    pub price: SkuPrice,
    pub size: SkuSize,
    pub quantity: SkuQuantity,
    pub availability_status: Option<String>,
    pub stock_level: Option<i64>,
    pub images: Vec<String>,
    pub allergens: Vec<String>,
    pub ingredients: Vec<String>,
}

#[derive(Serialize, Deserialize, Clone, Debug)]
pub struct StoredSku {
    pub id: i64,
    pub item_id: i64,
    /// Trumps `items.cheapest_by` entirely when set — see
    /// `shopping_list_items::cheapest_sku_id`. At most one SKU per item
    /// can be preferred at a time (see `db::skus::set_preferred`).
    pub is_preferred: bool,
    #[serde(flatten)]
    pub sku: Sku,
}
