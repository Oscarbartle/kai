//! Import a recipe from a web page — slice 1: fetch a URL, read the recipe
//! the page carries, and return a draft for previewing. Nothing is saved.
//!
//! How it works: most recipe sites embed the whole recipe as schema.org
//! `Recipe` JSON-LD in a `<script type="application/ld+json">` (name,
//! photo, yield, ingredient lines, steps) — in the same shape on every
//! site, so one reader covers them all. That is why "supported" below
//! means *a site we have checked against real pages*, not a per-site
//! scraper: adding a site is verifying it and adding a line to
//! [`SUPPORTED_SITES`], which is also what the app shows the user.
//!
//! Deliberately not here yet (later slices): splitting ingredient lines
//! into amount/unit/name, matching them to Pantry items, and creating
//! items/SKUs. `ingredient_lines` is the page's own text, untouched but
//! for HTML/entity cleanup.

use serde::Serialize;
use serde_json::Value;
use std::time::Duration;

/// A site the importer has been verified against. To add one: confirm it
/// with real recipe pages first (`cargo test -- --ignored live_`), then add
/// it here — the `domains` are what a pasted URL is matched on, and
/// `example_url` must be a real recipe page (it is the live test's input
/// and what the "try an example" link fills in).
#[derive(Serialize, Clone, Copy, Debug)]
pub struct SupportedSite {
    pub name: &'static str,
    pub domains: &'static [&'static str],
    pub example_url: &'static str,
    /// A known limitation worth telling the user about, shown beside the
    /// site ("no method"); `None` for a site that imports everything.
    pub note: Option<&'static str>,
}

pub const SUPPORTED_SITES: &[SupportedSite] = &[
    SupportedSite {
        name: "RecipeTin Eats",
        domains: &["recipetineats.com"],
        example_url: "https://www.recipetineats.com/thai-red-curry/",
        note: None,
    },
    SupportedSite {
        name: "BBC Good Food",
        domains: &["bbcgoodfood.com"],
        example_url: "https://www.bbcgoodfood.com/recipes/easy-pancakes",
        note: None,
    },
    SupportedSite {
        name: "Chelsea Sugar",
        domains: &["chelsea.co.nz"],
        example_url: "https://www.chelsea.co.nz/recipes/browse-recipes/banana-cake-chocolate-icing",
        note: None,
    },
    SupportedSite {
        name: "Edmonds",
        domains: &["edmondscooking.co.nz"],
        example_url: "https://edmondscooking.co.nz/recipes/cakes/banana-cake",
        // Its pages carry the ingredients but not the method, so the
        // method has to be typed in afterwards.
        note: Some("ingredients only, no method"),
    },
    SupportedSite {
        name: "Minimalist Baker",
        domains: &["minimalistbaker.com"],
        example_url: "https://minimalistbaker.com/honey-almond-snack-cake/",
        note: None,
    },
    SupportedSite {
        name: "King Arthur Baking",
        domains: &["kingarthurbaking.com"],
        example_url: "https://www.kingarthurbaking.com/recipes/cinnamon-roll-cake-recipe",
        note: None,
    },
    SupportedSite {
        name: "Epicurious",
        domains: &["epicurious.com"],
        example_url: "https://www.epicurious.com/recipes/food/views/diner-style-buttermilk-pancakes",
        note: None,
    },
    SupportedSite {
        name: "Bon Appetit",
        domains: &["bonappetit.com"],
        example_url: "https://www.bonappetit.com/recipe/rice-krispies-treats",
        note: None,
    },
];

// Checked and NOT listed (2026-10-06): Serious Eats and Simply Recipes. Their
// pages carry the recipe data, but both answered Kai's own requests with
// "402 Payment Required" every time (Allrecipes does too, for every page) —
// a bot wall, not something to work around — while a plain script got
// through now and then. A site that can't be promised to work is left off
// rather than listed and sometimes broken. Also checked: Woolworths and New
// World recipe pages (no recipe data in them), Annabel Langbein and Nadia
// Lim (no recipe links found to test — not a verdict).

/// What a page's recipe looks like once read. `yield_text` is the page's
/// own wording ("Makes 12", "4 servings") kept for display, because
/// `servings` — the first whole number in it — is a guess for sites that
/// word it loosely.
#[derive(Serialize, Clone, Debug, PartialEq)]
pub struct RecipeDraft {
    pub site: String,
    pub source_url: String,
    pub name: String,
    pub image_url: Option<String>,
    pub servings: Option<i64>,
    pub yield_text: Option<String>,
    pub ingredient_lines: Vec<String>,
    pub steps: Vec<String>,
}

fn supported_names() -> String {
    SUPPORTED_SITES.iter().map(|s| s.name).collect::<Vec<_>>().join(", ")
}

/// Which supported site a URL belongs to. Matches on the *host* — the
/// domain itself or any subdomain of it — never on a substring, so
/// `notrecipetineats.com` and `evil.com/recipetineats.com` are rejected.
pub fn site_for_url(url: &str) -> Result<&'static SupportedSite, String> {
    let parsed = reqwest::Url::parse(url.trim())
        .map_err(|_| "That doesn't look like a web address — paste the full link, starting with https://".to_string())?;
    if parsed.scheme() != "http" && parsed.scheme() != "https" {
        return Err("Only web addresses (http or https) can be imported".to_string());
    }
    let host = parsed
        .host_str()
        .ok_or("That web address has no site name in it")?
        .to_ascii_lowercase();
    SUPPORTED_SITES
        .iter()
        .find(|site| {
            site.domains
                .iter()
                .any(|d| host == *d || host.ends_with(&format!(".{d}")))
        })
        .ok_or_else(|| {
            format!(
                "{host} isn't a supported site yet. Supported: {}",
                supported_names()
            )
        })
}

// ---------------------------------------------------------------- fetching

const USER_AGENT: &str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 \
    (KHTML, like Gecko) Chrome/124.0 Safari/537.36";

pub async fn fetch_page(url: &str) -> Result<String, String> {
    let client = reqwest::Client::builder()
        .timeout(Duration::from_secs(20))
        .build()
        .map_err(|e| format!("Couldn't start the download: {e}"))?;
    let resp = client
        .get(url)
        .header("User-Agent", USER_AGENT)
        .header("Accept", "text/html,application/xhtml+xml")
        .header("Accept-Language", "en")
        .send()
        .await
        .map_err(|e| format!("Couldn't reach the site: {e}"))?;

    let status = resp.status();
    if status == reqwest::StatusCode::FORBIDDEN
        || status == reqwest::StatusCode::TOO_MANY_REQUESTS
        || status == reqwest::StatusCode::SERVICE_UNAVAILABLE
    {
        // Not worked around: some sites refuse automated downloads and
        // that is theirs to decide. The message says so rather than
        // pretending the page doesn't exist.
        return Err(format!(
            "The site refused the request ({status}). Some sites block automated downloads — try again in a minute, or a different recipe."
        ));
    }
    if status == reqwest::StatusCode::NOT_FOUND {
        return Err("That page wasn't found (404) — check the link".to_string());
    }
    if !status.is_success() {
        return Err(format!("The site answered with {status}"));
    }
    resp.text()
        .await
        .map_err(|e| format!("The download was interrupted: {e}"))
}

/// Fetch + read, for the `preview_recipe_from_url` command.
pub async fn preview_from_url(url: &str) -> Result<RecipeDraft, String> {
    let url = url.trim();
    let site = site_for_url(url)?;
    let html = fetch_page(url).await?;
    parse_recipe_page(&html, url, site.name)
}

// ----------------------------------------------------------------- reading

/// Every `<script type="application/ld+json">` body in the page.
fn ld_json_blocks(html: &str) -> Vec<&str> {
    // ASCII lowercasing keeps byte offsets identical, so positions found
    // in the lowercase copy index straight into the original.
    let lower = html.to_ascii_lowercase();
    let mut blocks = Vec::new();
    let mut from = 0;
    while let Some(start) = lower[from..].find("<script") {
        let tag_start = from + start;
        let Some(tag_end) = lower[tag_start..].find('>').map(|i| tag_start + i) else {
            break;
        };
        let tag = &lower[tag_start..tag_end];
        let Some(close) = lower[tag_end..].find("</script").map(|i| tag_end + i) else {
            break;
        };
        if tag.contains("application/ld+json") {
            blocks.push(&html[tag_end + 1..close]);
        }
        from = close + 1;
    }
    blocks
}

/// The first object whose `@type` is (or includes) `Recipe`, wherever it
/// is nested — top level, inside an `@graph`, inside a list.
fn find_recipe(value: &Value) -> Option<&Value> {
    match value {
        Value::Array(items) => items.iter().find_map(find_recipe),
        Value::Object(map) => {
            let is_recipe = match map.get("@type") {
                Some(Value::String(t)) => t == "Recipe",
                Some(Value::Array(ts)) => ts.iter().any(|t| t.as_str() == Some("Recipe")),
                _ => false,
            };
            if is_recipe {
                return Some(value);
            }
            map.values().find_map(find_recipe)
        }
        _ => None,
    }
}

fn decode_entities(s: &str) -> String {
    let mut out = String::with_capacity(s.len());
    let mut rest = s;
    while let Some(i) = rest.find('&') {
        out.push_str(&rest[..i]);
        let after = &rest[i + 1..];
        if let Some(semi) = after.find(';').filter(|&p| p <= 8) {
            let entity = &after[..semi];
            let decoded = match entity {
                "amp" => Some('&'),
                "lt" => Some('<'),
                "gt" => Some('>'),
                "quot" => Some('"'),
                "apos" => Some('\''),
                "nbsp" => Some(' '),
                e if e.starts_with("#x") || e.starts_with("#X") => {
                    u32::from_str_radix(&e[2..], 16).ok().and_then(char::from_u32)
                }
                e if e.starts_with('#') => e[1..].parse::<u32>().ok().and_then(char::from_u32),
                _ => None,
            };
            if let Some(c) = decoded {
                out.push(c);
                rest = &after[semi + 1..];
                continue;
            }
        }
        out.push('&');
        rest = after;
    }
    out.push_str(rest);
    out
}

/// Drops HTML tags (block-level ones become line breaks), decodes
/// entities, and tidies whitespace. Returns the non-empty lines.
fn text_lines(raw: &str) -> Vec<String> {
    let mut text = String::with_capacity(raw.len());
    let mut chars = raw.chars().peekable();
    while let Some(c) = chars.next() {
        let looks_like_tag = c == '<'
            && chars
                .peek()
                .is_some_and(|n| n.is_ascii_alphabetic() || *n == '/' || *n == '!');
        if !looks_like_tag {
            text.push(c);
            continue;
        }
        let mut tag = String::new();
        for t in chars.by_ref() {
            if t == '>' {
                break;
            }
            tag.push(t);
        }
        let name: String = tag
            .trim_start_matches('/')
            .chars()
            .take_while(|ch| ch.is_ascii_alphanumeric())
            .collect::<String>()
            .to_ascii_lowercase();
        if matches!(name.as_str(), "br" | "p" | "li" | "div" | "ol" | "ul" | "h1" | "h2" | "h3" | "h4") {
            text.push('\n');
        }
    }
    decode_entities(&text)
        .split('\n')
        .map(|line| line.split_whitespace().collect::<Vec<_>>().join(" "))
        .filter(|line| !line.is_empty())
        .collect()
}

/// A single-line field: everything joined onto one line.
fn inline_text(raw: &str) -> String {
    text_lines(raw).join(" ")
}

fn first_string(value: &Value) -> Option<String> {
    let s = inline_text(value.as_str()?);
    (!s.is_empty()).then_some(s)
}

/// `image` is a URL string, a list of them, an `ImageObject`, or a list of
/// those — take the first usable URL.
fn image_url(value: &Value) -> Option<String> {
    match value {
        Value::String(s) => {
            let s = s.trim();
            (!s.is_empty()).then(|| s.to_string())
        }
        Value::Array(items) => items.iter().find_map(image_url),
        Value::Object(map) => map
            .get("url")
            .or_else(|| map.get("contentUrl"))
            .and_then(image_url),
        _ => None,
    }
}

fn first_whole_number(s: &str) -> Option<i64> {
    let digits: String = s
        .chars()
        .skip_while(|c| !c.is_ascii_digit())
        .take_while(|c| c.is_ascii_digit())
        .collect();
    digits.parse().ok()
}

/// `recipeYield` is `4`, `"4"`, `"Makes 12"`, `"4 servings"`, `["1", "1
/// cup"]` or missing. Returns (servings guess, the page's own wording).
fn yield_info(value: Option<&Value>) -> (Option<i64>, Option<String>) {
    let Some(value) = value else {
        return (None, None);
    };
    let parts: Vec<String> = match value {
        Value::Number(n) => vec![n.to_string()],
        Value::String(s) => vec![inline_text(s)],
        Value::Array(items) => items
            .iter()
            .filter_map(|v| match v {
                Value::Number(n) => Some(n.to_string()),
                Value::String(s) => Some(inline_text(s)),
                _ => None,
            })
            .collect(),
        _ => vec![],
    };
    let parts: Vec<String> = parts.into_iter().filter(|p| !p.is_empty()).collect();
    if parts.is_empty() {
        return (None, None);
    }
    let servings = parts
        .iter()
        .find_map(|p| first_whole_number(p))
        .filter(|n| (1..=1000).contains(n));
    (servings, Some(parts.join(" / ")))
}

/// `recipeInstructions` is a list of `HowToStep`, a list of strings, lists
/// grouped in `HowToSection`s, or one big string — flatten all of it into
/// a plain list of steps.
fn instruction_steps(value: &Value, out: &mut Vec<String>) {
    match value {
        Value::String(s) => out.extend(text_lines(s)),
        Value::Array(items) => items.iter().for_each(|v| instruction_steps(v, out)),
        Value::Object(map) => {
            if let Some(inner) = map.get("itemListElement") {
                instruction_steps(inner, out);
            } else if let Some(text) = map.get("text").or_else(|| map.get("name")) {
                instruction_steps(text, out);
            }
        }
        _ => {}
    }
}

/// Reads the recipe out of a page's HTML.
pub fn parse_recipe_page(html: &str, source_url: &str, site: &str) -> Result<RecipeDraft, String> {
    let recipe = ld_json_blocks(html)
        .into_iter()
        // A page can carry several blocks, and one malformed one must not
        // hide a good one.
        .filter_map(|block| serde_json::from_str::<Value>(block.trim()).ok())
        .find_map(|json| find_recipe(&json).cloned())
        .ok_or("Couldn't find a recipe on that page — it may not be a recipe page, or the site may have changed")?;

    let name = recipe
        .get("name")
        .or_else(|| recipe.get("headline"))
        .and_then(first_string)
        .ok_or("The page has a recipe but no title Kai can read")?;

    let ingredient_lines: Vec<String> = recipe
        .get("recipeIngredient")
        .or_else(|| recipe.get("ingredients"))
        .and_then(Value::as_array)
        .map(|lines| lines.iter().filter_map(first_string).collect())
        .unwrap_or_default();
    if ingredient_lines.is_empty() {
        return Err("The page has a recipe, but no ingredient list Kai can read".to_string());
    }

    let mut steps = Vec::new();
    if let Some(instructions) = recipe.get("recipeInstructions") {
        instruction_steps(instructions, &mut steps);
    }

    let (servings, yield_text) = yield_info(recipe.get("recipeYield"));

    Ok(RecipeDraft {
        site: site.to_string(),
        source_url: source_url.trim().to_string(),
        name,
        image_url: recipe.get("image").and_then(image_url),
        servings,
        yield_text,
        ingredient_lines,
        steps,
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    fn page(json: &str) -> String {
        format!(
            r#"<html><head><title>x</title>
            <script type="application/ld+json">{json}</script></head><body></body></html>"#
        )
    }

    fn parse(json: &str) -> Result<RecipeDraft, String> {
        parse_recipe_page(&page(json), "https://example.com/r", "Example")
    }

    // ---- the shapes the real sites send (see CLAUDE.md for the probe) ----

    #[test]
    fn reads_a_typical_page_with_every_field() {
        let draft = parse(
            r#"{"@context":"https://schema.org","@type":"Recipe","name":"Thai Red Curry Paste",
                "image":["https://img.example/a.jpg","https://img.example/b.jpg"],
                "recipeYield":["1","1 cup"],
                "recipeIngredient":["2 tbsp lemongrass (, sliced (Note 2))","1/2 tsp ground coriander"],
                "recipeInstructions":[{"@type":"HowToStep","text":"Blend it."},{"@type":"HowToStep","text":"Simmer."}]}"#,
        )
        .unwrap();
        assert_eq!(draft.name, "Thai Red Curry Paste");
        assert_eq!(draft.site, "Example");
        assert_eq!(draft.image_url.as_deref(), Some("https://img.example/a.jpg"));
        assert_eq!(draft.servings, Some(1));
        assert_eq!(draft.yield_text.as_deref(), Some("1 / 1 cup"));
        assert_eq!(draft.ingredient_lines.len(), 2);
        assert_eq!(draft.ingredient_lines[0], "2 tbsp lemongrass (, sliced (Note 2))");
        assert_eq!(draft.steps, ["Blend it.", "Simmer."]);
    }

    #[test]
    fn finds_the_recipe_inside_a_graph_next_to_other_things() {
        let draft = parse(
            r#"{"@context":"https://schema.org","@graph":[
                {"@type":"WebSite","name":"The Site"},
                {"@type":["Recipe","Thing"],"name":"Pancakes","recipeYield":"Makes 12",
                 "recipeIngredient":["100g plain flour"],"recipeInstructions":"Whisk.\nCook."}]}"#,
        )
        .unwrap();
        assert_eq!(draft.name, "Pancakes");
        assert_eq!(draft.servings, Some(12));
        assert_eq!(draft.steps, ["Whisk.", "Cook."]);
    }

    #[test]
    fn yield_wording_varies_and_missing_is_fine() {
        let yield_of = |y: &str| {
            let json = format!(
                r#"{{"@type":"Recipe","name":"R","recipeIngredient":["x"]{y}}}"#
            );
            let d = parse(&json).unwrap();
            (d.servings, d.yield_text)
        };
        assert_eq!(yield_of(r#","recipeYield":"4 servings""#), (Some(4), Some("4 servings".into())));
        assert_eq!(yield_of(r#","recipeYield":"Makes 12""#).0, Some(12));
        assert_eq!(yield_of(r#","recipeYield":6"#), (Some(6), Some("6".into())));
        assert_eq!(yield_of(r#","recipeYield":"Serves 4-6""#).0, Some(4));
        assert_eq!(yield_of(r#","recipeYield":"a few""#), (None, Some("a few".into())));
        assert_eq!(yield_of(r#","recipeYield":"0""#).0, None, "0 servings is not a number we trust");
        assert_eq!(yield_of(""), (None, None));
    }

    #[test]
    fn instructions_in_every_shape() {
        let steps = |instr: &str| {
            parse(&format!(
                r#"{{"@type":"Recipe","name":"R","recipeIngredient":["x"],"recipeInstructions":{instr}}}"#
            ))
            .unwrap()
            .steps
        };
        // list of plain strings
        assert_eq!(steps(r#"["Mix.","Bake."]"#), ["Mix.", "Bake."]);
        // sections of steps
        assert_eq!(
            steps(r#"[{"@type":"HowToSection","name":"Dough","itemListElement":[
                {"@type":"HowToStep","text":"Knead."},{"@type":"HowToStep","text":"Rest."}]},
                {"@type":"HowToStep","text":"Bake."}]"#),
            ["Knead.", "Rest.", "Bake."]
        );
        // one string with markup
        assert_eq!(
            steps(r#""<p>Chop the onion.</p><p>Fry it.<br>Serve.</p>""#),
            ["Chop the onion.", "Fry it.", "Serve."]
        );
        // a step with only a name
        assert_eq!(steps(r#"[{"@type":"HowToStep","name":"Plate up"}]"#), ["Plate up"]);
        // none at all is allowed — some pages have ingredients but no method
        assert!(steps("null").is_empty());
    }

    #[test]
    fn images_in_every_shape() {
        let image = |img: &str| {
            parse(&format!(
                r#"{{"@type":"Recipe","name":"R","recipeIngredient":["x"],"image":{img}}}"#
            ))
            .unwrap()
            .image_url
        };
        assert_eq!(image(r#""https://i/a.jpg""#).as_deref(), Some("https://i/a.jpg"));
        assert_eq!(image(r#"{"@type":"ImageObject","url":"https://i/b.jpg"}"#).as_deref(), Some("https://i/b.jpg"));
        assert_eq!(
            image(r#"[{"@type":"ImageObject","url":"https://i/c.jpg"},"https://i/d.jpg"]"#).as_deref(),
            Some("https://i/c.jpg")
        );
        assert_eq!(image(r#"[]"#), None);
        assert_eq!(image(r#""""#), None);
    }

    #[test]
    fn markup_and_entities_in_text_are_cleaned() {
        let draft = parse(
            r#"{"@type":"Recipe","name":"Mac &amp; Cheese &#8211; the <em>best</em>",
                "recipeIngredient":["1 tbsp&nbsp;butter","2 cups   milk\n(whole)","<b>200g</b> cheddar &lt;grated&gt;","5&#xBD; oz pasta"]}"#,
        )
        .unwrap();
        assert_eq!(draft.name, "Mac & Cheese \u{2013} the best");
        assert_eq!(
            draft.ingredient_lines,
            ["1 tbsp butter", "2 cups milk (whole)", "200g cheddar <grated>", "5\u{bd} oz pasta"]
        );
    }

    #[test]
    fn a_bare_ampersand_or_angle_bracket_is_left_alone() {
        let draft = parse(
            r#"{"@type":"Recipe","name":"R","recipeIngredient":["salt & pepper","pieces <1 cm","AT&T not an entity;"]}"#,
        )
        .unwrap();
        assert_eq!(draft.ingredient_lines, ["salt & pepper", "pieces <1 cm", "AT&T not an entity;"]);
    }

    // ---- pages that can't be read ----

    #[test]
    fn a_page_with_no_recipe_says_so() {
        let err = parse(r#"{"@type":"Article","name":"Ten tips"}"#).unwrap_err();
        assert!(err.contains("Couldn't find a recipe"), "{err}");
        let err = parse_recipe_page("<html>no scripts at all</html>", "u", "S").unwrap_err();
        assert!(err.contains("Couldn't find a recipe"), "{err}");
    }

    #[test]
    fn a_recipe_without_ingredients_or_a_title_is_refused() {
        let err = parse(r#"{"@type":"Recipe","name":"Empty","recipeIngredient":[]}"#).unwrap_err();
        assert!(err.contains("no ingredient list"), "{err}");
        let err = parse(r#"{"@type":"Recipe","recipeIngredient":["1 egg"]}"#).unwrap_err();
        assert!(err.contains("no title"), "{err}");
    }

    #[test]
    fn a_broken_block_does_not_hide_a_good_one() {
        let html = r#"<script type="application/ld+json">{ not json at all </script>
            <script type="text/javascript">var x = {"@type":"Recipe"};</script>
            <SCRIPT TYPE="application/LD+JSON" id="b">{"@type":"Recipe","name":"Good","recipeIngredient":["1 egg"]}</SCRIPT>"#;
        let draft = parse_recipe_page(html, "u", "S").unwrap();
        assert_eq!(draft.name, "Good");
    }

    // ---- which URLs belong to a supported site ----

    #[test]
    fn urls_match_on_the_host_not_a_substring() {
        let ok = |u: &str| site_for_url(u).map(|s| s.name);
        assert_eq!(ok("https://www.recipetineats.com/thai-red-curry/"), Ok("RecipeTin Eats"));
        assert_eq!(ok("https://recipetineats.com/x"), Ok("RecipeTin Eats"));
        assert_eq!(ok("  HTTPS://WWW.BBCGOODFOOD.COM/recipes/easy-pancakes  "), Ok("BBC Good Food"));
        assert_eq!(ok("http://bbcgoodfood.com/a"), Ok("BBC Good Food"));
        assert_eq!(ok("https://m.bbcgoodfood.com/a"), Ok("BBC Good Food"), "a subdomain of a supported domain");
        assert!(ok("https://www.seriouseats.com/x").is_err(), "known not to work from the app, so not listed");

        for bad in [
            "https://notrecipetineats.com/x",
            "https://recipetineats.com.evil.example/x",
            "https://evil.example/recipetineats.com/x",
            "https://evil.example/?u=https://www.bbcgoodfood.com/x",
        ] {
            let err = ok(bad).unwrap_err();
            assert!(err.contains("isn't a supported site"), "{bad}: {err}");
            assert!(err.contains("RecipeTin Eats") && err.contains("BBC Good Food"), "lists what is supported: {err}");
        }
        assert!(ok("not a url").unwrap_err().contains("web address"));
        assert!(ok("ftp://www.recipetineats.com/x").unwrap_err().contains("http"));
        assert!(ok("").is_err());
    }

    #[test]
    fn every_supported_site_has_a_working_example_and_unique_domains() {
        let mut seen = std::collections::HashSet::new();
        for site in SUPPORTED_SITES {
            assert_eq!(
                site_for_url(site.example_url).map(|s| s.name),
                Ok(site.name),
                "{}'s own example URL must route back to it",
                site.name
            );
            for d in site.domains {
                assert!(seen.insert(*d), "domain {d} listed twice");
            }
        }
    }

    // ---- against the real sites (network): `cargo test -- --ignored live_` ----

    #[tokio::test]
    #[ignore = "hits the real sites"]
    async fn live_every_supported_site_still_imports() {
        let mut failures = Vec::new();
        for site in SUPPORTED_SITES {
            match preview_from_url(site.example_url).await {
                Ok(d) => {
                    println!(
                        "{:16} ok: {:?} | serves {:?} ({:?}) | {} ingredients, {} steps | image {}",
                        site.name,
                        d.name,
                        d.servings,
                        d.yield_text,
                        d.ingredient_lines.len(),
                        d.steps.len(),
                        d.image_url.is_some()
                    );
                    let needs_method = site.note.is_none();
                    if d.ingredient_lines.len() < 3 || (needs_method && d.steps.is_empty()) || d.image_url.is_none() {
                        failures.push(format!("{}: thin result {d:?}", site.name));
                    }
                }
                Err(e) => failures.push(format!("{}: {e}", site.name)),
            }
        }
        assert!(failures.is_empty(), "{}", failures.join("\n"));
    }
}
