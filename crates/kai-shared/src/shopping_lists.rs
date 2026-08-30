use serde::{Deserialize, Serialize};

#[derive(Serialize, Deserialize, Clone, Debug)]
pub struct ShoppingList {
    pub id: i64,
    pub name: String,
    pub created_at: String,
}
