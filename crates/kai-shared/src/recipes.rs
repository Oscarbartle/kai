use serde::{Deserialize, Serialize};

#[derive(Serialize, Deserialize, Clone, Debug)]
pub struct Recipe {
    pub id: i64,
    pub name: String,
    pub method: Option<String>,
    /// What the ingredient amounts on `recipe_items` are actually for —
    /// needed to scale a recipe before it hits a shopping list later.
    pub servings: Option<i64>,
    pub source_url: Option<String>,
    pub image_url: Option<String>,
    pub created_at: String,
}
