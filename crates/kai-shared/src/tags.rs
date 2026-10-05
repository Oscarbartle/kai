use serde::{Deserialize, Serialize};

#[derive(Serialize, Deserialize, Clone, Debug)]
pub struct Tag {
    pub id: i64,
    pub name: String,
    /// User override for the sidebar toggle's emoji — `None` means "use
    /// the auto-picked one" (a client-side guess off the name, see
    /// +page.svelte). Never shown on the plain-text tag pills.
    pub emoji: Option<String>,
}

/// A batch edit to who carries one tag, applied together or not at all.
/// Removals are applied before additions; an id that is already in the
/// requested state (tagging something already tagged, untagging something
/// that is not) is quietly fine.
#[derive(Serialize, Deserialize, Clone, Debug, Default)]
pub struct TagMembershipChanges {
    #[serde(default)]
    pub add_item_ids: Vec<i64>,
    #[serde(default)]
    pub remove_item_ids: Vec<i64>,
    #[serde(default)]
    pub add_recipe_ids: Vec<i64>,
    #[serde(default)]
    pub remove_recipe_ids: Vec<i64>,
}
