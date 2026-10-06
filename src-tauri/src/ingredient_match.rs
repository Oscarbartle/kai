//! Suggests which existing Pantry item an ingredient name refers to.
//!
//! A *guess to be reviewed*, never a decision: the result carries a
//! confidence and the runners-up, and the review table shows all of it.
//!
//! How names are compared: both sides are lowercased, split into words,
//! stripped of words that don't change what a thing is (`fresh`, `large`,
//! `of`), and reduced to a singular form (`tomatoes` → `tomato`). Then:
//!
//! - same words → an exact match (`Eggs` ↔ `Egg`, `Fresh coriander` ↔
//!   `Coriander`);
//! - one side's words all appear in the other's → a close match, scored by
//!   how much of the longer name the shorter one covers (`onions` ↔
//!   `Brown Onion`; `rapeseed or sesame oil` ↔ `Sesame Oil`);
//! - only the last word in common (`red onion` ↔ `Brown Onion`, `sesame
//!   oil` ↔ `Olive Oil`) → offered as a suggestion but *not* preselected —
//!   that is as likely to be the wrong oil as the right onion;
//! - anything else → by overlap, low.
//!
//! Words that make a different product (`crushed`, `ground`, `dried`) are
//! deliberately *not* ignored, so `Crushed Garlic` and `Garlic` are close,
//! not identical.

use serde::Serialize;
use std::collections::BTreeSet;

#[derive(Serialize, Clone, Debug, PartialEq)]
pub struct ItemSuggestion {
    pub item_id: i64,
    pub name: String,
    pub score: f64,
}

#[derive(Serialize, Clone, Copy, Debug, PartialEq)]
#[serde(rename_all = "snake_case")]
pub enum Confidence {
    /// Same item, give or take plurals and filler words.
    Strong,
    /// Probably, but worth a look.
    Check,
    /// Nothing good enough to preselect (there may still be suggestions).
    None,
}

#[derive(Serialize, Clone, Debug, PartialEq)]
pub struct MatchResult {
    pub confidence: Confidence,
    /// Best first; at most five; only things worth showing.
    pub suggestions: Vec<ItemSuggestion>,
}

const STRONG: f64 = 0.95;
const CHECK: f64 = 0.55;
const WORTH_SHOWING: f64 = 0.25;
/// Shared last word only: shown, never preselected.
const SAME_LAST_WORD: f64 = 0.45;

const FILLER: &[&str] = &[
    "a", "an", "the", "of", "or", "and", "with", "in", "to", "for", "plus", "fresh", "large", "small",
    "medium", "big", "free", "range", "organic", "boneless", "skinless", "lean", "good", "quality",
    "ripe", "homemade", "store", "bought",
];

fn singular(word: &str) -> String {
    let n = word.len();
    if n > 4 && word.ends_with("ies") {
        format!("{}y", &word[..n - 3])
    } else if n > 4 && word.ends_with("oes") {
        word[..n - 2].to_string()
    } else if n > 3 && word.ends_with('s') && !word.ends_with("ss") && !word.ends_with("us") {
        word[..n - 1].to_string()
    } else {
        word.to_string()
    }
}

/// The comparable words of a name, in order, filler removed.
fn words(name: &str) -> Vec<String> {
    name.to_lowercase()
        .split(|c: char| !c.is_alphanumeric())
        .filter(|w| !w.is_empty() && !FILLER.contains(w))
        .map(singular)
        .collect()
}

fn score(ingredient: &[String], item: &[String]) -> f64 {
    if ingredient.is_empty() || item.is_empty() {
        return 0.0;
    }
    let a: BTreeSet<&String> = ingredient.iter().collect();
    let b: BTreeSet<&String> = item.iter().collect();
    if a == b {
        return 1.0;
    }
    let shared = a.intersection(&b).count();
    if shared == a.len() || shared == b.len() {
        // One name is wholly inside the other.
        let (small, large) = if a.len() < b.len() { (a.len(), b.len()) } else { (b.len(), a.len()) };
        return 0.6 + 0.3 * (small as f64 / large as f64);
    }
    let union = a.union(&b).count();
    let overlap = 0.7 * shared as f64 / union as f64;
    if ingredient.last() == item.last() {
        overlap.max(SAME_LAST_WORD)
    } else {
        overlap
    }
}

/// Ranks `items` (`(id, name)`) as candidates for an ingredient's `name`.
pub fn match_ingredient(name: &str, items: &[(i64, &str)]) -> MatchResult {
    let ingredient = words(name);
    let mut ranked: Vec<ItemSuggestion> = items
        .iter()
        .map(|(id, item_name)| ItemSuggestion {
            item_id: *id,
            name: item_name.to_string(),
            score: score(&ingredient, &words(item_name)),
        })
        .filter(|s| s.score >= WORTH_SHOWING)
        .collect();
    // Best first; among equals the shorter, more general name, then A–Z, so
    // the order never depends on how the items happened to be listed.
    ranked.sort_by(|x, y| {
        y.score
            .total_cmp(&x.score)
            .then(x.name.len().cmp(&y.name.len()))
            .then(x.name.to_lowercase().cmp(&y.name.to_lowercase()))
    });
    ranked.truncate(5);

    let confidence = match ranked.first().map(|s| s.score) {
        Some(s) if s >= STRONG => Confidence::Strong,
        Some(s) if s >= CHECK => Confidence::Check,
        _ => Confidence::None,
    };
    MatchResult { confidence, suggestions: ranked }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn pantry() -> Vec<(i64, &'static str)> {
        vec![
            (1, "Brown Onion"),
            (2, "Eggs"),
            (3, "Olive Oil"),
            (4, "Sesame Oil"),
            (5, "Coriander"),
            (6, "Ground Coriander"),
            (7, "Chicken Thighs"),
            (8, "Crushed Garlic"),
            (9, "Mushrooms"),
            (10, "Canned Tomatoes"),
            (11, "Soy Sauce"),
            (12, "Fish Sauce"),
        ]
    }

    fn best(name: &str) -> (Confidence, Option<i64>) {
        let r = match_ingredient(name, &pantry());
        (r.confidence, r.suggestions.first().map(|s| s.item_id))
    }

    #[test]
    fn same_item_despite_plurals_case_and_filler() {
        assert_eq!(best("Eggs"), (Confidence::Strong, Some(2)));
        assert_eq!(best("egg"), (Confidence::Strong, Some(2)));
        assert_eq!(best("large eggs"), (Confidence::Strong, Some(2)));
        assert_eq!(best("Fresh coriander"), (Confidence::Strong, Some(5)));
        assert_eq!(best("Ground coriander"), (Confidence::Strong, Some(6)), "the more specific item wins an exact match");
        assert_eq!(best("SESAME OIL"), (Confidence::Strong, Some(4)));
        assert_eq!(best("Tomatoes, canned"), (Confidence::Strong, Some(10)), "word order does not matter");
    }

    #[test]
    fn one_name_inside_the_other_is_worth_a_look() {
        let r = match_ingredient("Onions", &pantry());
        assert_eq!(r.confidence, Confidence::Check);
        assert_eq!(r.suggestions[0].item_id, 1);
        assert!((r.suggestions[0].score - 0.75).abs() < 1e-9);

        assert_eq!(best("Chestnut mushrooms"), (Confidence::Check, Some(9)));
        assert_eq!(best("Rapeseed or sesame oil"), (Confidence::Check, Some(4)));
        assert_eq!(best("Garlic"), (Confidence::Check, Some(8)), "plain garlic vs Crushed Garlic is close, not identical");
    }

    #[test]
    fn a_shared_last_word_alone_is_suggested_but_not_preselected() {
        let r = match_ingredient("Red onion", &pantry());
        assert_eq!(r.confidence, Confidence::None);
        assert_eq!(r.suggestions[0].item_id, 1, "Brown Onion is still offered first");

        let r = match_ingredient("Fish sauce", &pantry());
        assert_eq!(r.confidence, Confidence::Strong);
        let r = match_ingredient("Oyster sauce", &pantry());
        assert_eq!(r.confidence, Confidence::None, "another sauce is not the same sauce");
        let ids: Vec<i64> = r.suggestions.iter().map(|s| s.item_id).collect();
        assert!(ids.contains(&11) && ids.contains(&12));
    }

    #[test]
    fn unrelated_things_have_no_match_and_no_noise() {
        let r = match_ingredient("Chicken breast", &pantry());
        assert_eq!(r.confidence, Confidence::None);
        assert!(r.suggestions.iter().all(|s| s.score < CHECK));
        let r = match_ingredient("Tamari", &pantry());
        assert_eq!((r.confidence, r.suggestions.len()), (Confidence::None, 0));
        assert_eq!(match_ingredient("", &pantry()).confidence, Confidence::None);
        assert_eq!(match_ingredient("Onion", &[]).suggestions, vec![]);
    }

    #[test]
    fn at_most_five_best_first_and_stable() {
        let items: Vec<(i64, &str)> = vec![
            (1, "Oil"),
            (2, "Olive Oil"),
            (3, "Sesame Oil"),
            (4, "Coconut Oil"),
            (5, "Sunflower Oil"),
            (6, "Rapeseed Oil"),
            (7, "Vegetable Oil"),
        ];
        let r = match_ingredient("Oil", &items);
        assert_eq!(r.suggestions.len(), 5);
        assert_eq!(r.suggestions[0].item_id, 1, "the exact one first");
        let again = match_ingredient("Oil", &items.iter().rev().cloned().collect::<Vec<_>>());
        assert_eq!(r, again, "the order of the pantry must not change the answer");
    }

    #[test]
    fn singular_forms() {
        for (plural, single) in [
            ("tomatoes", "tomato"),
            ("potatoes", "potato"),
            ("berries", "berry"),
            ("eggs", "egg"),
            ("olives", "olive"),
            ("chillis", "chilli"),
            ("asparagus", "asparagus"),
            ("hummus", "hummus"),
            ("glass", "glass"),
            ("oil", "oil"),
            ("peas", "pea"),
        ] {
            assert_eq!(singular(plural), single, "{plural}");
        }
    }
}
