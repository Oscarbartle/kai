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
