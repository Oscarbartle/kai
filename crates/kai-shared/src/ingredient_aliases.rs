use serde::{Deserialize, Serialize};

/// "When a recipe says *this*, it means *that* pantry item" — learned from
/// the user's own choices in the recipe importer so the next import starts
/// from them. `alias` is the ingredient's name in normalised form (see
/// `ingredient_match::alias_key` in the desktop app: lowercase, filler
/// dropped, singular, words sorted), not what the recipe literally said.
#[derive(Serialize, Deserialize, Clone, Debug, PartialEq)]
pub struct IngredientAlias {
    pub alias: String,
    pub item_id: i64,
}
