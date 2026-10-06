//! Recipe import, slice 2: everything between "the page's ingredient lines"
//! and "a saved recipe".
//!
//! - [`analyze`] parses each line and matches it against the Pantry — the
//!   review table's starting point. Pure: it only reads what it is given.
//! - [`create_recipe`] saves the user's *reviewed* choices through the same
//!   `Backend` everything else uses (so it works in local and remote mode).
//!
//! Saving is several writes with no transaction across them (a remote
//! server has no "save the whole recipe at once" call), so it is built to
//! fail cleanly: everything is validated and merged *before* the first
//! write, and if a write still fails the recipe and any items this import
//! created are deleted again — the user gets an error and an unchanged
//! database, not a half-built recipe.

use crate::backend::Backend;
use crate::db::items::Item;
use crate::db::recipe_items::VALID_UNITS;
use crate::ingredient_match::{match_ingredient, Confidence, ItemSuggestion};
use crate::ingredient_parse::{parse_ingredient_line, ParsedIngredient};
use crate::woolworths::Sku;
use serde::{Deserialize, Serialize};

// ---------------------------------------------------------------- analyzing

#[derive(Serialize, Clone, Debug)]
pub struct AnalyzedIngredient {
    #[serde(flatten)]
    pub parsed: ParsedIngredient,
    pub confidence: Confidence,
    pub suggestions: Vec<ItemSuggestion>,
}

#[derive(Serialize, Clone, Debug)]
pub struct ItemRef {
    pub id: i64,
    pub name: String,
}

#[derive(Serialize, Clone, Debug)]
pub struct Analysis {
    pub rows: Vec<AnalyzedIngredient>,
    /// Every Pantry item, A–Z, for the "pick a different item" list.
    pub items: Vec<ItemRef>,
}

pub fn analyze(lines: &[String], items: &[Item]) -> Analysis {
    let candidates: Vec<(i64, &str)> = items.iter().map(|i| (i.id, i.name.as_str())).collect();
    let rows = lines
        .iter()
        .map(|line| {
            let parsed = parse_ingredient_line(line);
            let found = match_ingredient(&parsed.name, &candidates);
            AnalyzedIngredient {
                parsed,
                confidence: found.confidence,
                suggestions: found.suggestions,
            }
        })
        .collect();
    let mut refs: Vec<ItemRef> = items
        .iter()
        .map(|i| ItemRef { id: i.id, name: i.name.clone() })
        .collect();
    refs.sort_by_key(|r| r.name.to_lowercase());
    Analysis { rows, items: refs }
}

// ------------------------------------------------------------------- saving

/// One reviewed ingredient: either an existing item (`item_id`) or a new
/// one to create (`new_item_name`) — exactly one of the two.
#[derive(Deserialize, Clone, Debug)]
pub struct ImportIngredient {
    pub item_id: Option<i64>,
    pub new_item_name: Option<String>,
    pub amount: Option<f64>,
    pub unit: Option<String>,
    /// New items only: is it perishable? (Defaults to yes, like every new
    /// item. A non-perishable ingredient is left off a shopping list when
    /// its recipe is added to one.)
    #[serde(default)]
    pub new_item_perishable: Option<bool>,
    /// New items only: Woolworths products to link, already fetched in full
    /// (allergens and all) by the wizard. Ignored if the name turns out to
    /// match an item that already exists — that item is used as it is.
    #[serde(default)]
    pub new_item_skus: Vec<Sku>,
}

#[derive(Deserialize, Clone, Debug)]
pub struct ImportRequest {
    pub name: String,
    pub source_url: String,
    pub image_url: Option<String>,
    pub servings: Option<i64>,
    pub steps: Vec<String>,
    pub ingredients: Vec<ImportIngredient>,
}

#[derive(Serialize, Clone, Debug)]
pub struct ImportOutcome {
    pub recipe_id: i64,
    /// Names of the items this import had to create.
    pub created_items: Vec<String>,
    pub ingredient_count: usize,
    /// How many Woolworths products were linked to the new items.
    pub skus_added: usize,
}

#[derive(Clone, Debug, PartialEq)]
pub enum Target {
    Existing(i64),
    Create(String),
}

/// What to set up on an item this import creates.
#[derive(Clone, Debug)]
pub struct NewItemPlan {
    pub is_perishable: bool,
    pub skus: Vec<Sku>,
}

impl PartialEq for NewItemPlan {
    fn eq(&self, other: &Self) -> bool {
        self.is_perishable == other.is_perishable
            && self.skus.iter().map(|s| &s.sku).eq(other.skus.iter().map(|s| &s.sku))
    }
}

#[derive(Clone, Debug, PartialEq)]
pub struct Planned {
    pub target: Target,
    pub amount: Option<f64>,
    pub unit: Option<String>,
    /// Set only when `target` is `Create`.
    pub new_item: Option<NewItemPlan>,
}

/// The same product twice (it can be picked twice) is linked once.
fn unique_skus(skus: &[Sku]) -> Vec<Sku> {
    let mut seen = std::collections::HashSet::new();
    skus.iter().filter(|s| seen.insert(s.sku.clone())).cloned().collect()
}

/// Validates the request and folds it into the rows that will be saved:
/// a recipe holds each item once, so two lines for the same item become
/// one (their amounts added when the units agree).
pub fn plan(req: &ImportRequest, items: &[Item]) -> Result<Vec<Planned>, String> {
    if req.name.trim().is_empty() {
        return Err("The recipe needs a name".to_string());
    }
    if req.ingredients.is_empty() {
        return Err("Choose at least one ingredient to import — every line is set to skip".to_string());
    }

    let mut planned: Vec<Planned> = Vec::new();
    for (index, line) in req.ingredients.iter().enumerate() {
        let n = index + 1;
        let target = match (line.item_id, line.new_item_name.as_deref().map(str::trim)) {
            (Some(id), None) => {
                if !items.iter().any(|i| i.id == id) {
                    return Err(format!("Ingredient {n}: that item no longer exists"));
                }
                Target::Existing(id)
            }
            (None, Some(name)) if !name.is_empty() => {
                // Same rule as everywhere else in the app: reuse an item
                // with that name (any capitalisation) rather than make a twin.
                match items.iter().find(|i| i.name.trim().eq_ignore_ascii_case(name)) {
                    Some(existing) => Target::Existing(existing.id),
                    None => Target::Create(name.to_string()),
                }
            }
            (None, Some(_)) => return Err(format!("Ingredient {n}: the new item needs a name")),
            _ => return Err(format!("Ingredient {n}: choose an item, or skip the line")),
        };

        let (amount, unit) = match (line.amount, line.unit.as_deref().filter(|u| !u.is_empty())) {
            (None, _) => (None, None),
            (Some(a), _) if !a.is_finite() || a <= 0.0 => {
                return Err(format!("Ingredient {n}: the amount must be more than zero"));
            }
            (Some(_), None) => {
                return Err(format!("Ingredient {n}: pick a unit for the amount, or clear the amount"));
            }
            (Some(a), Some(u)) if VALID_UNITS.contains(&u) => (Some(a), Some(u.to_string())),
            (Some(_), Some(u)) => return Err(format!("Ingredient {n}: '{u}' isn't a unit Kai uses")),
        };

        let same_target = |p: &Planned| match (&p.target, &target) {
            (Target::Create(a), Target::Create(b)) => a.eq_ignore_ascii_case(b),
            (a, b) => a == b,
        };
        match planned.iter_mut().find(|p| same_target(p)) {
            None => {
                let new_item = matches!(target, Target::Create(_)).then(|| NewItemPlan {
                    is_perishable: line.new_item_perishable.unwrap_or(true),
                    skus: unique_skus(&line.new_item_skus),
                });
                planned.push(Planned { target, amount, unit, new_item })
            }
            Some(existing) => {
                // Two lines for one new item: keep the first's settings, but
                // don't lose products picked on the second.
                if let Some(have) = existing.new_item.as_mut() {
                    if have.skus.is_empty() {
                        have.skus = unique_skus(&line.new_item_skus);
                    }
                }
                match (existing.amount, amount) {
                (_, None) => {}
                (None, Some(_)) => {
                    existing.amount = amount;
                    existing.unit = unit;
                }
                (Some(a), Some(b)) if existing.unit == unit => existing.amount = Some(a + b),
                (Some(_), Some(_)) => {
                    let name = match &target {
                        Target::Existing(id) => items.iter().find(|i| i.id == *id).map(|i| i.name.clone()).unwrap_or_default(),
                        Target::Create(name) => name.clone(),
                    };
                    return Err(format!(
                        "Two lines use \"{name}\" with different units ({} and {}) — change one so they match, or skip one",
                        existing.unit.as_deref().unwrap_or("none"),
                        unit.as_deref().unwrap_or("none"),
                    ));
                }
                }
            }
        }
    }
    Ok(planned)
}

pub async fn create_recipe(backend: &dyn Backend, req: ImportRequest) -> Result<ImportOutcome, String> {
    let items = backend.list_items().await?;
    let planned = plan(&req, &items)?;
    run_plan(backend, &req, &planned).await
}

/// Performs the writes; on any failure undoes what it did.
async fn run_plan(backend: &dyn Backend, req: &ImportRequest, planned: &[Planned]) -> Result<ImportOutcome, String> {
    let recipe = backend.create_recipe(req.name.trim()).await?;
    let mut created: Vec<(i64, String)> = Vec::new();

    match write_everything(backend, recipe.id, req, planned, &mut created).await {
        Ok(skus_added) => Ok(ImportOutcome {
            recipe_id: recipe.id,
            created_items: created.into_iter().map(|(_, name)| name).collect(),
            ingredient_count: planned.len(),
            skus_added,
        }),
        Err(error) => {
            let mut leftovers = Vec::new();
            if let Err(e) = backend.delete_recipe(recipe.id).await {
                leftovers.push(format!("the recipe ({e})"));
            }
            for (id, name) in &created {
                if let Err(e) = backend.delete_item(*id).await {
                    leftovers.push(format!("the new item \"{name}\" ({e})"));
                }
            }
            if leftovers.is_empty() {
                Err(format!("{error}. Nothing was saved."))
            } else {
                Err(format!(
                    "{error}. Kai also couldn't fully undo it — remove {} by hand.",
                    leftovers.join(" and ")
                ))
            }
        }
    }
}

async fn write_everything(
    backend: &dyn Backend,
    recipe_id: i64,
    req: &ImportRequest,
    planned: &[Planned],
    created: &mut Vec<(i64, String)>,
) -> Result<usize, String> {
    let mut skus_added = 0;
    for line in planned {
        let item_id = match &line.target {
            Target::Existing(id) => *id,
            Target::Create(name) => {
                let item = backend.create_item(name).await?;
                created.push((item.id, item.name.clone()));
                if let Some(setup) = &line.new_item {
                    if !setup.is_perishable {
                        backend.set_item_perishable(item.id, false).await?;
                    }
                    for sku in &setup.skus {
                        backend.save_sku_to_item(item.id, sku).await?;
                        skus_added += 1;
                    }
                }
                item.id
            }
        };
        backend.add_item_to_recipe(recipe_id, item_id).await?;
        backend
            .set_recipe_item_quantity(recipe_id, item_id, line.amount, line.unit.as_deref())
            .await?;
    }
    if let Some(servings) = req.servings {
        backend.update_recipe_servings(recipe_id, Some(servings)).await?;
    }
    if !req.source_url.trim().is_empty() {
        backend.update_recipe_source_url(recipe_id, req.source_url.trim()).await?;
    }
    if let Some(image) = req.image_url.as_deref().map(str::trim).filter(|s| !s.is_empty()) {
        backend.set_recipe_image_url(recipe_id, Some(image)).await?;
    }
    let method = req.steps.iter().map(|s| s.trim()).filter(|s| !s.is_empty()).collect::<Vec<_>>().join("\n");
    if !method.is_empty() {
        backend.update_recipe_method(recipe_id, &method).await?;
    }
    Ok(skus_added)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::backend::{ItemsBackend, LocalBackend, RecipeItemsBackend, RecipesBackend, SkusBackend};
    use rusqlite::Connection;
    use std::sync::{Arc, Mutex};

    fn backend_with_conn() -> (LocalBackend, Arc<Mutex<Connection>>) {
        let mut conn = Connection::open_in_memory().unwrap();
        conn.pragma_update(None, "foreign_keys", true).unwrap();
        crate::db::migrations().to_latest(&mut conn).unwrap();
        let shared = Arc::new(Mutex::new(conn));
        (LocalBackend::new(shared.clone()), shared)
    }

    fn backend() -> LocalBackend {
        backend_with_conn().0
    }

    fn item(id: i64, name: &str) -> Item {
        Item {
            id,
            name: name.into(),
            is_perishable: true,
            image_url: None,
            cheapest_by: "total".into(),
            created_at: String::new(),
        }
    }

    fn existing(id: i64, amount: Option<f64>, unit: Option<&str>) -> ImportIngredient {
        ImportIngredient { item_id: Some(id), new_item_name: None, amount, unit: unit.map(String::from), new_item_perishable: None, new_item_skus: vec![] }
    }

    fn new_item(name: &str, amount: Option<f64>, unit: Option<&str>) -> ImportIngredient {
        ImportIngredient { item_id: None, new_item_name: Some(name.into()), amount, unit: unit.map(String::from), new_item_perishable: None, new_item_skus: vec![] }
    }

    fn plain_new() -> NewItemPlan {
        NewItemPlan { is_perishable: true, skus: vec![] }
    }

    fn sku(code: &str, name: &str) -> Sku {
        Sku {
            provider: "woolworths".into(),
            sku: code.into(),
            name: name.into(),
            brand: Some("kikkoman".into()),
            variety: None,
            price: crate::woolworths::SkuPrice { sale_price: Some(8.69), ..Default::default() },
            size: crate::woolworths::SkuSize { volume_size: Some("600mL".into()), ..Default::default() },
            quantity: crate::woolworths::SkuQuantity { unit: "Each".into(), ..Default::default() },
            availability_status: Some("In Stock".into()),
            stock_level: None,
            images: vec![],
            allergens: vec!["Contains Soy".into()],
            ingredients: vec![],
        }
    }

    fn request(ingredients: Vec<ImportIngredient>) -> ImportRequest {
        ImportRequest {
            name: "Chow mein".into(),
            source_url: "https://www.bbcgoodfood.com/recipes/x".into(),
            image_url: Some("https://img.example/a.jpg".into()),
            servings: Some(2),
            steps: vec!["Boil.".into(), "  ".into(), "Fry.".into()],
            ingredients,
        }
    }

    // ---- analyze ----

    #[test]
    fn analysis_pairs_each_line_with_a_guess_and_lists_the_pantry() {
        let items = vec![item(1, "Brown Onion"), item(2, "Eggs"), item(3, "Apple")];
        let lines: Vec<String> = ["2 large eggs", "1 small red onion (100g), finely chopped", "1½ tsp tamari", "2 cups flour"]
            .iter()
            .map(|s| s.to_string())
            .collect();
        let a = analyze(&lines, &items);
        assert_eq!(a.rows.len(), 4);

        assert_eq!((a.rows[0].parsed.amount, a.rows[0].parsed.unit.as_deref()), (Some(2.0), Some("count")));
        assert_eq!((a.rows[0].confidence, a.rows[0].suggestions[0].item_id), (Confidence::Strong, 2));

        assert_eq!(a.rows[1].confidence, Confidence::None, "red onion vs brown onion is only suggested");
        assert_eq!(a.rows[1].suggestions[0].item_id, 1);

        assert_eq!(a.rows[2].confidence, Confidence::None);
        assert!(a.rows[2].suggestions.is_empty());

        assert_eq!(a.rows[3].parsed.unresolved_quantity.as_deref(), Some("2 cups"));
        assert_eq!(a.rows[3].parsed.amount, None);

        let names: Vec<_> = a.items.iter().map(|i| i.name.as_str()).collect();
        assert_eq!(names, ["Apple", "Brown Onion", "Eggs"], "A–Z");
    }

    #[test]
    fn analysis_serializes_flat_for_the_review_table() {
        let a = analyze(&["2 eggs".to_string()], &[item(2, "Eggs")]);
        let v = serde_json::to_value(&a.rows[0]).unwrap();
        for key in ["raw", "amount", "unit", "unresolved_quantity", "note", "name", "confidence", "suggestions"] {
            assert!(v.get(key).is_some(), "{key} missing from {v}");
        }
        assert_eq!(v["confidence"], "strong");
    }

    // ---- plan ----

    #[test]
    fn plan_reuses_items_by_name_and_merges_duplicates() {
        let items = vec![item(1, "Onion"), item(2, "Tamari")];
        let planned = plan(
            &request(vec![
                existing(1, Some(1.0), Some("count")),
                new_item("  onion ", Some(2.0), Some("count")), // same item, different words
                new_item("Rice vinegar", Some(1.0), Some("tbsp")),
                new_item("rice VINEGAR", Some(2.0), Some("tbsp")), // same new item twice
                new_item("Tamari", Some(1.5), Some("tsp")),
                new_item("Salt", None, None),
                new_item("salt", Some(1.0), Some("tsp")), // an amount beats no amount
            ]),
            &items,
        )
        .unwrap();
        assert_eq!(
            planned,
            vec![
                Planned { target: Target::Existing(1), amount: Some(3.0), unit: Some("count".into()), new_item: None },
                Planned { target: Target::Create("Rice vinegar".into()), amount: Some(3.0), unit: Some("tbsp".into()), new_item: Some(plain_new()) },
                Planned { target: Target::Existing(2), amount: Some(1.5), unit: Some("tsp".into()), new_item: None },
                Planned { target: Target::Create("Salt".into()), amount: Some(1.0), unit: Some("tsp".into()), new_item: Some(plain_new()) },
            ]
        );
    }

    #[test]
    fn plan_refuses_unit_clashes_rather_than_guessing() {
        let items = vec![item(1, "Butter")];
        let err = plan(
            &request(vec![existing(1, Some(100.0), Some("g")), existing(1, Some(1.0), Some("tbsp"))]),
            &items,
        )
        .unwrap_err();
        assert!(err.contains("Butter") && err.contains("different units"), "{err}");
    }

    #[test]
    fn plan_rejects_bad_requests_with_specific_messages() {
        let items = vec![item(1, "Onion")];
        let bad = |ingredients: Vec<ImportIngredient>| plan(&request(ingredients), &items).unwrap_err();

        assert!(plan(&ImportRequest { name: "  ".into(), ..request(vec![existing(1, None, None)]) }, &items)
            .unwrap_err()
            .contains("needs a name"));
        assert!(bad(vec![]).contains("at least one ingredient"));
        assert!(bad(vec![existing(99, None, None)]).contains("no longer exists"));
        let both = ImportIngredient { new_item_name: Some("x".into()), ..existing(1, None, None) };
        assert!(bad(vec![both]).contains("choose an item"));
        let neither = ImportIngredient { item_id: None, ..existing(1, None, None) };
        assert!(bad(vec![neither]).contains("choose an item"));
        assert!(bad(vec![new_item("   ", None, None)]).contains("needs a name"));
        assert!(bad(vec![existing(1, Some(0.0), Some("g"))]).contains("more than zero"));
        assert!(bad(vec![existing(1, Some(-2.0), Some("g"))]).contains("more than zero"));
        assert!(bad(vec![existing(1, Some(f64::NAN), Some("g"))]).contains("more than zero"));
        assert!(bad(vec![existing(1, Some(2.0), None)]).contains("pick a unit"));
        assert!(bad(vec![existing(1, Some(2.0), Some(""))]).contains("pick a unit"));
        assert!(bad(vec![existing(1, Some(2.0), Some("cup"))]).contains("isn't a unit"));
    }

    #[test]
    fn a_unit_without_an_amount_is_dropped() {
        let planned = plan(&request(vec![existing(1, None, Some("g"))]), &[item(1, "Onion")]).unwrap();
        assert_eq!((planned[0].amount, planned[0].unit.clone()), (None, None));
    }

    // ---- new items with a perishable flag and Woolworths products ----

    #[test]
    fn plan_carries_the_new_item_setup_through_a_merge() {
        let (a_sku, b_sku) = (sku("270415", "highmark soy sauce golden"), sku("103725", "kikkoman soy sauce"));

        // The first line's settings win; a product picked twice is linked once.
        let mut first = new_item("Soy sauce", Some(1.0), Some("tbsp"));
        first.new_item_perishable = Some(false);
        first.new_item_skus = vec![a_sku.clone(), a_sku.clone()];
        let mut second = new_item("soy SAUCE", Some(2.0), Some("tbsp"));
        second.new_item_skus = vec![b_sku.clone()];
        let planned = plan(&request(vec![first, second]), &[item(1, "Onion")]).unwrap();
        assert_eq!(planned.len(), 1);
        let setup = planned[0].new_item.as_ref().unwrap();
        assert!(!setup.is_perishable);
        assert_eq!(setup.skus.iter().map(|s| s.sku.as_str()).collect::<Vec<_>>(), ["270415"]);
        assert_eq!(planned[0].amount, Some(3.0));

        // ...but products picked only on the second line are not lost.
        let bare = new_item("Tamari", None, None);
        let mut later = new_item("tamari", None, None);
        later.new_item_skus = vec![b_sku];
        let planned = plan(&request(vec![bare, later]), &[]).unwrap();
        let setup = planned[0].new_item.as_ref().unwrap();
        assert!(setup.is_perishable, "perishable by default, like every other new item");
        assert_eq!(setup.skus.len(), 1);
    }

    #[test]
    fn a_new_name_that_matches_an_existing_item_uses_it_and_ignores_the_setup() {
        let mut line = new_item("onion", Some(1.0), Some("count"));
        line.new_item_perishable = Some(false);
        line.new_item_skus = vec![sku("1", "some onion")];
        let planned = plan(&request(vec![line]), &[item(7, "Onion")]).unwrap();
        assert_eq!(planned[0].target, Target::Existing(7));
        assert_eq!(planned[0].new_item, None, "an item you already have is never reconfigured by an import");
    }

    #[tokio::test]
    async fn new_items_are_created_with_their_flag_and_products() {
        let backend = backend();
        let mut soy = new_item("Soy sauce", Some(2.0), Some("tbsp"));
        soy.new_item_perishable = Some(false);
        soy.new_item_skus = vec![sku("270415", "highmark soy sauce golden"), sku("103725", "kikkoman soy sauce")];
        let outcome = create_recipe(&backend, request(vec![soy, new_item("Salt", None, None)])).await.unwrap();
        assert_eq!(outcome.skus_added, 2);
        assert_eq!(outcome.created_items, ["Soy sauce", "Salt"]);

        let items = backend.list_items().await.unwrap();
        let soy_item = items.iter().find(|i| i.name == "Soy sauce").unwrap();
        let salt_item = items.iter().find(|i| i.name == "Salt").unwrap();
        assert!(!soy_item.is_perishable, "the wizard's toggle was applied");
        assert!(salt_item.is_perishable);

        let skus = backend.list_skus_for_item(soy_item.id).await.unwrap();
        assert_eq!(skus.len(), 2);
        let kikkoman = skus.iter().find(|s| s.sku.sku == "103725").unwrap();
        assert_eq!(kikkoman.sku.allergens, ["Contains Soy"], "allergens (a real requirement here) are kept");
        assert_eq!(kikkoman.sku.price.sale_price, Some(8.69));
        assert!(backend.list_skus_for_item(salt_item.id).await.unwrap().is_empty());
    }

    #[tokio::test]
    async fn a_failure_also_removes_the_products_it_had_linked() {
        let (backend, conn) = backend_with_conn();
        let planned = vec![
            Planned {
                target: Target::Create("Tamari".into()),
                amount: None,
                unit: None,
                new_item: Some(NewItemPlan { is_perishable: false, skus: vec![sku("42", "tamari")] }),
            },
            Planned { target: Target::Existing(9999), amount: None, unit: None, new_item: None },
        ];
        let err = run_plan(&backend, &request(vec![]), &planned).await.unwrap_err();
        assert!(err.ends_with("Nothing was saved."), "{err}");

        let count = |table: &str| -> i64 {
            conn.lock().unwrap().query_row(&format!("SELECT COUNT(*) FROM {table}"), [], |r| r.get(0)).unwrap()
        };
        assert_eq!((count("items"), count("skus"), count("recipes")), (0, 0, 0), "nothing at all is left behind");
    }

    // ---- real pages through the whole read → parse → match pipeline ----
    // `cargo test -p kai --lib live_ -- --ignored --nocapture` prints what
    // the review table would start from, which is the way to eyeball a
    // site before adding it to the supported list.

    #[tokio::test]
    #[ignore = "hits the real sites"]
    async fn live_every_supported_site_parses_into_a_review() {
        let pantry: Vec<Item> = [
            "Brown Onion", "Eggs", "Milk", "Plain Flour", "Olive Oil", "Sesame Oil", "Garlic", "Ginger",
            "Coriander", "Mushrooms", "Chicken Thighs", "Soy Sauce", "Sugar", "Butter",
        ]
        .iter()
        .enumerate()
        .map(|(i, n)| item(i as i64 + 1, n))
        .collect();

        for site in crate::recipe_import::SUPPORTED_SITES {
            let draft = crate::recipe_import::preview_from_url(site.example_url).await.expect(site.name);
            let analysis = analyze(&draft.ingredient_lines, &pantry);
            println!("\n=== {} — {} ===", site.name, draft.name);
            for row in &analysis.rows {
                let p = &row.parsed;
                let amount = match (p.amount, &p.unit, &p.unresolved_quantity) {
                    (Some(a), Some(u), _) => format!("{a} {u}"),
                    (_, _, Some(q)) => format!("[blank: recipe says \"{q}\"]"),
                    _ => "(no amount)".to_string(),
                };
                let best = row.suggestions.first().map(|s| format!("{} ({:.2})", s.name, s.score)).unwrap_or("-".into());
                println!("{:<62} | {:<28} | {:<18} | {:?} {}", p.raw.chars().take(62).collect::<String>(), amount, p.name, row.confidence, best);
            }
            assert!(analysis.rows.iter().all(|r| !r.parsed.name.is_empty()), "{}: a line parsed to no name", site.name);
        }
    }

    // ---- saving, against a real (in-memory) database ----

    #[tokio::test]
    async fn saves_the_recipe_with_everything_the_review_chose() {
        let backend = backend();
        let onion = backend.create_item("Onion").await.unwrap();
        let outcome = create_recipe(
            &backend,
            request(vec![
                existing(onion.id, Some(2.0), Some("count")),
                new_item("Tamari", Some(1.5), Some("tsp")),
                new_item("Salt", None, None),
            ]),
        )
        .await
        .unwrap();

        assert_eq!(outcome.created_items, ["Tamari", "Salt"]);
        assert_eq!(outcome.ingredient_count, 3);

        let recipe = backend.list_recipes().await.unwrap().into_iter().find(|r| r.id == outcome.recipe_id).unwrap();
        assert_eq!(recipe.name, "Chow mein");
        assert_eq!(recipe.servings, Some(2));
        assert_eq!(recipe.source_url.as_deref(), Some("https://www.bbcgoodfood.com/recipes/x"));
        assert_eq!(recipe.image_url.as_deref(), Some("https://img.example/a.jpg"));
        assert_eq!(recipe.method.as_deref(), Some("Boil.\nFry."), "blank steps dropped, one per line");

        let ingredients = backend.list_recipe_ingredients(outcome.recipe_id).await.unwrap();
        assert_eq!(ingredients.len(), 3);
        let by_name = |n: &str| ingredients.iter().find(|i| i.name == n).unwrap();
        assert_eq!((by_name("Onion").amount, by_name("Onion").unit.as_deref()), (Some(2.0), Some("count")));
        assert_eq!((by_name("Tamari").amount, by_name("Tamari").unit.as_deref()), (Some(1.5), Some("tsp")));
        assert_eq!((by_name("Salt").amount, by_name("Salt").unit.clone()), (None, None));
        assert_eq!(backend.list_items().await.unwrap().len(), 3, "Onion was reused, the other two created");
    }

    #[tokio::test]
    async fn a_failure_part_way_undoes_everything_it_made() {
        let backend = backend();
        let onion = backend.create_item("Onion").await.unwrap();
        let before_items = backend.list_items().await.unwrap().len();

        // Bypass `plan` to force a real failure inside the writes: the
        // last item does not exist, so linking it fails after the recipe
        // and a new item have already been created.
        let req = request(vec![]);
        let planned = vec![
            Planned { target: Target::Existing(onion.id), amount: Some(1.0), unit: Some("count".into()), new_item: None },
            Planned { target: Target::Create("Tamari".into()), amount: None, unit: None, new_item: None },
            Planned { target: Target::Existing(9999), amount: None, unit: None, new_item: None },
        ];
        let err = run_plan(&backend, &req, &planned).await.unwrap_err();

        assert!(err.ends_with("Nothing was saved."), "{err}");
        assert!(backend.list_recipes().await.unwrap().is_empty(), "the half-built recipe is gone");
        let items = backend.list_items().await.unwrap();
        assert_eq!(items.len(), before_items, "the item this import created is gone too");
        assert!(items.iter().any(|i| i.name == "Onion"), "an item that already existed is never touched");
        assert!(!items.iter().any(|i| i.name == "Tamari"));
    }

    #[tokio::test]
    async fn nothing_is_written_when_the_request_is_invalid() {
        let backend = backend();
        let onion = backend.create_item("Onion").await.unwrap();
        let err = create_recipe(
            &backend,
            request(vec![existing(onion.id, Some(1.0), Some("g")), existing(onion.id, Some(1.0), Some("tsp"))]),
        )
        .await
        .unwrap_err();
        assert!(err.contains("different units"), "{err}");
        assert!(backend.list_recipes().await.unwrap().is_empty(), "validated before the first write");
    }
}
