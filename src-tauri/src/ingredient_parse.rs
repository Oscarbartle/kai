//! Turns one free-text ingredient line from a recipe page into an amount,
//! a unit and a clean name — by rules, not guesswork:
//!
//! - **`g` / `mL`** — metric amounts, and the conversions that are exact
//!   (kg, L, oz, lb). Metric in brackets, e.g. `1/2 pound (225g)`, beats a
//!   non-metric amount, because it is the recipe's own number.
//! - **`tsp` / `tbsp`** — kept as written (nominal in this app).
//! - **`count`** — a number of things: `2 large eggs`, `1 can`, `2 tins`.
//! - **Blank, with the recipe's wording kept** — anything with no honest
//!   conversion: cups (a cup of milk and a cup of flour weigh differently,
//!   which this app deliberately does not model), cloves, bunches,
//!   pinches, "5cm piece". The amount is left empty and the recipe's own
//!   words ("2 cups") are returned so the user can convert them
//!   themselves. Never a silent guess.
//!
//! Deliberately conservative about names: only words that describe how an
//! ingredient is prepared or sized are dropped (`finely chopped`, `large`);
//! words that can make a different product (`crushed`, `ground`, `dried`,
//! `frozen`, `whole`) are kept, because the Pantry has items like
//! "Crushed Garlic" and "Dried Mint".

use serde::Serialize;

#[derive(Serialize, Clone, Debug, PartialEq)]
pub struct ParsedIngredient {
    pub raw: String,
    pub amount: Option<f64>,
    /// One of the app's recipe units: `g`, `mL`, `count`, `tsp`, `tbsp`.
    pub unit: Option<String>,
    /// The recipe's own quantity wording when it could not be turned into
    /// one of the units above ("2 cups", "4 cloves", "a pinch").
    pub unresolved_quantity: Option<String>,
    /// Something worth a glance in the review ("range 2-3: used 3").
    pub note: Option<String>,
    /// What the ingredient is, cleaned up — used for matching and as the
    /// default name of a new item.
    pub name: String,
}

// ------------------------------------------------------------ number reading

/// Replaces vulgar-fraction characters with plain text: `1½` → `1 1/2`.
fn normalize(raw: &str) -> String {
    let mut out = String::with_capacity(raw.len() + 4);
    for c in raw.chars() {
        let frac = match c {
            '½' => Some("1/2"),
            '¼' => Some("1/4"),
            '¾' => Some("3/4"),
            '⅓' => Some("1/3"),
            '⅔' => Some("2/3"),
            '⅛' => Some("1/8"),
            '⅜' => Some("3/8"),
            '⅝' => Some("5/8"),
            '⅞' => Some("7/8"),
            _ => None,
        };
        if let Some(f) = frac {
            if out.chars().last().is_some_and(|p| p.is_ascii_digit()) {
                out.push(' ');
            }
            out.push_str(f);
        } else if c == '–' || c == '—' {
            out.push('-');
        } else if c == '\u{a0}' || c == '\u{2009}' || c == '\u{202f}' {
            out.push(' ');
        } else {
            out.push(c);
        }
    }
    out.split_whitespace().collect::<Vec<_>>().join(" ")
}

/// Reads one number at the start: `2`, `1.5`, `1/2`, or `1 1/2`.
/// Returns the value and how many bytes it used.
fn read_number(s: &str) -> Option<(f64, usize)> {
    let bytes = s.as_bytes();
    let mut i = 0;
    while i < bytes.len() && bytes[i].is_ascii_digit() {
        i += 1;
    }
    if i == 0 {
        return None;
    }
    let mut value: f64;
    // a decimal
    if i < bytes.len() && bytes[i] == b'.' && bytes.get(i + 1).is_some_and(u8::is_ascii_digit) {
        let mut j = i + 1;
        while j < bytes.len() && bytes[j].is_ascii_digit() {
            j += 1;
        }
        return Some((s[..j].parse().ok()?, j));
    }
    // a plain fraction: 1/2
    if i < bytes.len() && bytes[i] == b'/' {
        if let Some((den, used)) = read_digits(&s[i + 1..]) {
            if den != 0.0 {
                return Some((s[..i].parse::<f64>().ok()? / den, i + 1 + used));
            }
        }
    }
    value = s[..i].parse().ok()?;
    // a mixed number: 1 1/2
    if bytes.get(i) == Some(&b' ') {
        if let Some((num, used_num)) = read_digits(&s[i + 1..]) {
            let after = i + 1 + used_num;
            if bytes.get(after) == Some(&b'/') {
                if let Some((den, used_den)) = read_digits(&s[after + 1..]) {
                    if den != 0.0 {
                        value += num / den;
                        return Some((value, after + 1 + used_den));
                    }
                }
            }
        }
    }
    Some((value, i))
}

fn read_digits(s: &str) -> Option<(f64, usize)> {
    let n = s.bytes().take_while(u8::is_ascii_digit).count();
    (n > 0).then(|| (s[..n].parse().unwrap_or(0.0), n))
}

/// A quantity at the start of the line, possibly a range (`2-3`, `2 to 3`).
/// Returns (amount, the range's lower end if it was a range, bytes used).
fn read_quantity(s: &str) -> Option<(f64, Option<f64>, usize)> {
    let (first, used) = read_number(s)?;
    let rest = &s[used..];
    for sep in ["-", " - ", " to ", "-to-"] {
        if let Some(after) = rest.strip_prefix(sep) {
            if let Some((second, used2)) = read_number(after) {
                if second >= first {
                    return Some((second, Some(first), used + sep.len() + used2));
                }
            }
        }
    }
    Some((first, None, used))
}

// ---------------------------------------------------------------- brackets

/// Splits out every bracketed part, nested ones included. Returns the line
/// with them removed, and their contents.
fn split_brackets(s: &str) -> (String, Vec<String>) {
    let mut outside = String::new();
    let mut inside = Vec::new();
    let mut depth = 0usize;
    let mut current = String::new();
    for c in s.chars() {
        match c {
            '(' => {
                if depth > 0 {
                    current.push(c);
                }
                depth += 1;
            }
            ')' if depth > 0 => {
                depth -= 1;
                if depth == 0 {
                    inside.push(std::mem::take(&mut current));
                } else {
                    current.push(c);
                }
            }
            _ if depth > 0 => current.push(c),
            _ => outside.push(c),
        }
    }
    if depth > 0 {
        // Unbalanced: treat the unclosed text as bracketed, not as name.
        inside.push(current);
    }
    (outside.split_whitespace().collect::<Vec<_>>().join(" "), inside)
}

/// A metric amount inside the brackets: `(225g)`, `(1L)`, `(28-ounce; 800g)`.
fn metric_in_brackets(brackets: &[String]) -> Option<(f64, &'static str)> {
    for text in brackets {
        let lower = text.to_ascii_lowercase();
        let b = lower.as_bytes();
        let mut i = 0;
        while i < b.len() {
            if b[i].is_ascii_digit() && (i == 0 || !b[i - 1].is_ascii_alphanumeric()) {
                if let Some((value, used)) = read_number(&lower[i..]) {
                    let mut j = i + used;
                    while b.get(j) == Some(&b' ') {
                        j += 1;
                    }
                    let word: String = lower[j..].chars().take_while(|c| c.is_ascii_alphabetic()).collect();
                    match word.as_str() {
                        "g" | "gram" | "grams" => return Some((value, "g")),
                        "kg" | "kilo" | "kilos" => return Some((value * 1000.0, "g")),
                        "ml" => return Some((value, "mL")),
                        "l" | "litre" | "litres" | "liter" | "liters" => return Some((value * 1000.0, "mL")),
                        _ => {}
                    }
                    i += used.max(1);
                    continue;
                }
            }
            i += 1;
        }
    }
    None
}

// ------------------------------------------------------------------- units

#[derive(Debug, PartialEq)]
enum UnitKind {
    Mass(f64),
    Volume(f64),
    Tsp,
    Tbsp,
    /// A discrete pack: a can, a jar.
    Pack,
    /// A real unit, but one with no honest g/mL conversion.
    NoConversion,
}

fn classify_unit(word: &str) -> Option<UnitKind> {
    use UnitKind::*;
    Some(match word.to_ascii_lowercase().trim_end_matches('.') {
        "g" | "gr" | "gram" | "grams" => Mass(1.0),
        "kg" | "kgs" | "kilo" | "kilos" | "kilogram" | "kilograms" => Mass(1000.0),
        "oz" | "ounce" | "ounces" => Mass(28.3495),
        "lb" | "lbs" | "pound" | "pounds" => Mass(453.592),
        "ml" | "millilitre" | "millilitres" | "milliliter" | "milliliters" => Volume(1.0),
        "cl" => Volume(10.0),
        "dl" => Volume(100.0),
        "l" | "ltr" | "litre" | "litres" | "liter" | "liters" => Volume(1000.0),
        "tsp" | "tsps" | "teaspoon" | "teaspoons" => Tsp,
        "tbsp" | "tbsps" | "tbs" | "tablespoon" | "tablespoons" => Tbsp,
        "can" | "cans" | "tin" | "tins" | "jar" | "jars" | "packet" | "packets" | "pack" | "packs"
        | "bottle" | "bottles" | "tub" | "tubs" | "bag" | "bags" | "box" | "boxes" | "block" | "blocks" => Pack,
        // Volumes whose weight depends on what is in them, and things that
        // are not a measure at all.
        "cup" | "cups" | "pint" | "pints" | "quart" | "quarts" | "gallon" | "gallons" | "clove"
        | "cloves" | "bunch" | "bunches" | "handful" | "handfuls" | "pinch" | "pinches" | "dash"
        | "dashes" | "sprig" | "sprigs" | "slice" | "slices" | "piece" | "pieces" | "stick" | "sticks"
        | "head" | "heads" | "stalk" | "stalks" | "knob" | "knobs" | "cm" | "mm" | "inch" | "inches"
        | "splash" | "drizzle" | "glug" | "rasher" | "rashers" | "fillet" | "fillets" | "sheet" | "sheets" => {
            NoConversion
        }
        _ => return None,
    })
}

/// Words that, as the *last* word of a name ("garlic cloves", "celery
/// stalks"), are a measure rather than part of what the thing is.
fn trailing_measure(word: &str) -> bool {
    matches!(
        word.to_ascii_lowercase().as_str(),
        "clove" | "cloves" | "sprig" | "sprigs" | "stalk" | "stalks" | "head" | "heads"
    )
}

// -------------------------------------------------------------------- name

/// Words that only describe preparation or size — dropped from the front
/// of a name. (Not `crushed`/`ground`/`dried`/`frozen`/`whole`: those can
/// be a different product.)
const LEADING_NOISE: &[&str] = &[
    "large", "small", "medium", "big", "finely", "roughly", "coarsely", "thickly", "thinly",
    "freshly", "chopped", "sliced", "diced", "minced", "grated", "trimmed", "halved",
    "quartered", "cubed", "shredded", "softened", "melted", "beaten", "drained", "rinsed", "ripe",
    "fresh", "about", "approx", "approximately", "of",
];

/// A word that starts a "how to prepare it" tail: `onion peeled and
/// chopped`. The name is cut before it (only once at least one word has
/// been kept).
const TAIL_STARTERS: &[&str] = &[
    "chopped", "sliced", "diced", "minced", "grated", "peeled", "trimmed", "halved", "quartered",
    "cubed", "shredded", "softened", "melted", "beaten", "drained", "rinsed", "cut", "removed",
    "finely", "roughly", "coarsely", "thickly", "thinly", "freshly", "plus", "for", "to", "at",
    "optional", "preferably", "divided", "packed", "sifted",
];

/// Prep words that, on something sold in a can or jar, are the product
/// itself ("chopped tomatoes", "sliced peaches") rather than a cooking step.
const FORM_WORDS: &[&str] = &[
    "chopped", "diced", "sliced", "minced", "grated", "shredded", "cubed", "halved", "quartered",
];

/// `packaged`: the line's unit is a can/tin/jar/packet, so a leading form
/// word is part of what is being bought and is kept.
fn clean_name(s: &str, packaged: bool) -> String {
    // Everything after the first comma is a preparation note.
    let head = s.split(',').next().unwrap_or("");
    let mut words: Vec<&str> = head.split_whitespace().collect();

    // "piece of ginger", "bunch of coriander"
    while words.len() > 2 && words.get(1).is_some_and(|w| w.eq_ignore_ascii_case("of"))
        && classify_unit(words[0]).is_some()
    {
        words.drain(0..2);
    }
    while words.first().is_some_and(|w| {
        let w = w.trim_matches(|c: char| !c.is_alphanumeric()).to_ascii_lowercase();
        LEADING_NOISE.contains(&w.as_str()) && !(packaged && FORM_WORDS.contains(&w.as_str()))
    }) && words.len() > 1
    {
        words.remove(0);
    }
    if let Some(cut) = words
        .iter()
        .enumerate()
        .skip(1)
        .find(|(_, w)| {
            let w = w.trim_matches(|c: char| !c.is_alphanumeric()).to_ascii_lowercase();
            TAIL_STARTERS.contains(&w.as_str())
        })
        .map(|(i, _)| i)
    {
        words.truncate(cut);
    }
    // a trailing "optional"/"to serve" can survive the cut above
    let joined = words.join(" ");
    let joined = joined.trim_matches(|c: char| c == '-' || c == ':' || c.is_whitespace());
    let mut chars = joined.chars();
    match chars.next() {
        Some(first) => first.to_uppercase().collect::<String>() + chars.as_str(),
        None => String::new(),
    }
}

fn round_amount(x: f64) -> f64 {
    if x >= 100.0 {
        x.round()
    } else {
        (x * 10.0).round() / 10.0
    }
}

// -------------------------------------------------------------------- parse

pub fn parse_ingredient_line(raw: &str) -> ParsedIngredient {
    let normalized = normalize(raw);
    let (line, brackets) = split_brackets(&normalized);
    let metric = metric_in_brackets(&brackets);

    let mut result = ParsedIngredient {
        raw: raw.trim().to_string(),
        amount: None,
        unit: None,
        unresolved_quantity: None,
        note: None,
        name: String::new(),
    };

    let Some((quantity, range_low, used)) = read_quantity(&line) else {
        // No number. "a pinch of salt", "a bunch of coriander", "salt".
        let words: Vec<&str> = line.split_whitespace().collect();
        let skip = usize::from(words.first().is_some_and(|w| matches!(w.to_ascii_lowercase().as_str(), "a" | "an" | "some")));
        if let Some(word) = words.get(skip).filter(|w| matches!(classify_unit(w), Some(UnitKind::NoConversion))) {
            result.unresolved_quantity = Some(words[..=skip].join(" "));
            let rest = words[skip + 1..].join(" ");
            result.name = clean_name(&rest, false);
            let _ = word;
        } else {
            result.name = clean_name(&line, false);
        }
        return result;
    };

    let mut rest = line[used..].trim_start().to_string();
    // "2 x 400g cans": a multiplied pack size. Not worked out — shown as
    // the recipe wrote it, for the user to turn into an amount.
    {
        let mut tokens = rest.split_whitespace();
        if matches!(tokens.next(), Some("x" | "X" | "\u{d7}")) {
            let size = tokens.next().unwrap_or("");
            let mut wording = format!("{} x {}", line[..used].trim(), size);
            let mut remaining: Vec<&str> = tokens.collect();
            if remaining.first().is_some_and(|w| matches!(classify_unit(w), Some(UnitKind::Pack))) {
                wording.push(' ');
                wording.push_str(remaining.remove(0));
            }
            result.unresolved_quantity = Some(wording);
            result.name = clean_name(&remaining.join(" "), false);
            return result;
        }
    }
    // "2 x 400g" is left to the review: not handled, not guessed.
    let quantity_text_end = |rest_after: &str| line[..line.len() - rest_after.len()].trim().to_string();

    // A leading "fl oz" is a volume, not a weight.
    let mut kind: Option<UnitKind> = None;
    let mut unit_word = String::new();
    let lower_rest = rest.to_ascii_lowercase();
    if lower_rest.starts_with("fl oz") || lower_rest.starts_with("fl. oz") || lower_rest.starts_with("fluid ounce") {
        kind = Some(UnitKind::NoConversion);
        unit_word = rest.split_whitespace().take(2).collect::<Vec<_>>().join(" ");
        let n = unit_word.len();
        rest = rest[n..].trim_start().to_string();
    } else {
        let word: String = rest
            .chars()
            .take_while(|c| c.is_ascii_alphabetic() || *c == '.')
            .collect();
        if !word.is_empty() {
            // "100g" has no gap, "5cm piece" none either — both read the same.
            let boundary_ok = rest[word.len()..].chars().next().map_or(true, |c| !c.is_alphanumeric());
            if boundary_ok {
                if let Some(k) = classify_unit(&word) {
                    kind = Some(k);
                    unit_word = word.clone();
                    rest = rest[word.len()..].trim_start().to_string();
                }
            }
        }
    }

    let (mut amount, mut note) = (quantity, None::<String>);
    if let Some(low) = range_low {
        note = Some(format!("The recipe gives a range ({}-{}); the larger end is used", fmt_num(low), fmt_num(quantity)));
    }
    let quantity_wording = quantity_text_end(&rest);

    let mut unit: Option<&'static str> = None;
    let mut unresolved: Option<String> = None;
    match kind {
        Some(UnitKind::Mass(f)) => {
            // oz/lb are exact conversions, but the recipe's own metric
            // number in brackets is better when it has one.
            if f != 1.0 && f != 1000.0 {
                if let Some((v, u)) = metric {
                    amount = v;
                    unit = Some(u);
                    note = Some("Used the metric amount from the brackets".to_string());
                } else {
                    amount = round_amount(amount * f);
                    unit = Some("g");
                }
            } else {
                amount = round_amount(amount * f);
                unit = Some("g");
            }
        }
        Some(UnitKind::Volume(f)) => {
            amount = round_amount(amount * f);
            unit = Some("mL");
        }
        Some(UnitKind::Tsp) => unit = Some("tsp"),
        Some(UnitKind::Tbsp) => unit = Some("tbsp"),
        Some(UnitKind::Pack) => {
            if let Some((v, u)) = metric {
                amount = v;
                unit = Some(u);
                note = Some("Used the size from the brackets".to_string());
            } else {
                unit = Some("count");
            }
        }
        Some(UnitKind::NoConversion) => {
            // cups, pints, quarts: use the brackets' metric if there is
            // one ("1 quart (1L)"); otherwise leave it for the user.
            let volume_word = matches!(
                unit_word.to_ascii_lowercase().as_str(),
                "cup" | "cups" | "pint" | "pints" | "quart" | "quarts" | "gallon" | "gallons" | "fl oz" | "fl. oz" | "fluid ounce"
            );
            if let (true, Some((v, u))) = (volume_word, metric) {
                amount = v;
                unit = Some(u);
                note = Some("Used the metric amount from the brackets".to_string());
            } else {
                unresolved = Some(quantity_wording.clone());
            }
        }
        None => {
            // No unit word: a count of things ("2 large eggs").
            unit = Some("count");
        }
    }

    let mut name = clean_name(&rest, matches!(kind, Some(UnitKind::Pack)));
    // "4 garlic cloves": the measure is the last word of the name.
    if unresolved.is_none() && unit == Some("count") {
        let words: Vec<&str> = name.split_whitespace().collect();
        if words.len() >= 2 && trailing_measure(words[words.len() - 1]) {
            unresolved = Some(format!("{} {}", fmt_num(quantity), words[words.len() - 1]));
            name = clean_name(&words[..words.len() - 1].join(" "), false);
        }
    }

    if unresolved.is_some() {
        result.unresolved_quantity = unresolved;
        result.note = note;
    } else {
        result.amount = Some(amount);
        result.unit = unit.map(str::to_string);
        // A weight in brackets next to a plain count is worth showing.
        if note.is_none() && unit == Some("count") {
            if let Some((v, u)) = metric {
                note = Some(format!("The recipe also gives {}{} in brackets", fmt_num(v), u));
            }
        }
        result.note = note;
    }
    result.name = name;
    result
}

fn fmt_num(x: f64) -> String {
    if (x - x.round()).abs() < 0.005 {
        format!("{}", x.round() as i64)
    } else {
        format!("{x:.2}").trim_end_matches('0').trim_end_matches('.').to_string()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    /// (amount, unit, name) — the three things a review row is built from.
    fn p(line: &str) -> (Option<f64>, Option<String>, String) {
        let r = parse_ingredient_line(line);
        (r.amount, r.unit, r.name)
    }

    fn g(amount: f64, name: &str) -> (Option<f64>, Option<String>, String) {
        (Some(amount), Some("g".into()), name.into())
    }

    fn unresolved(line: &str) -> (Option<String>, String) {
        let r = parse_ingredient_line(line);
        assert_eq!(r.amount, None, "{line}: amount must stay blank");
        assert_eq!(r.unit, None, "{line}: unit must stay blank");
        (r.unresolved_quantity, r.name)
    }

    // ---- the real lines seen on BBC Good Food, RecipeTin Eats, Serious Eats ----

    #[test]
    fn real_bbc_chow_mein_lines() {
        assert_eq!(p("2 wholemeal noodle nests (85g)"), (Some(2.0), Some("count".into()), "Wholemeal noodle nests".into()));
        assert_eq!(p("2 tsp rapeseed or sesame oil"), (Some(2.0), Some("tsp".into()), "Rapeseed or sesame oil".into()));
        assert_eq!(p("200g lean fillet steak fat removed and cut into strips"), g(200.0, "Lean fillet steak fat"));
        assert_eq!(p("1 small red onion (100g), finely chopped"), (Some(1.0), Some("count".into()), "Red onion".into()));
        assert_eq!(p("15g piece of ginger peeled and finely chopped"), g(15.0, "Ginger"));
        assert_eq!(p("160g chestnut mushrooms thickly sliced"), g(160.0, "Chestnut mushrooms"));
        assert_eq!(unresolved("2 garlic cloves finely chopped"), (Some("2 cloves".into()), "Garlic".into()));
        assert_eq!(p("160g ready-to-eat beansprouts"), g(160.0, "Ready-to-eat beansprouts"));
        assert_eq!(p("1½ tsp tamari"), (Some(1.5), Some("tsp".into()), "Tamari".into()));
        assert_eq!(p("1 tbsp brown rice vinegar"), (Some(1.0), Some("tbsp".into()), "Brown rice vinegar".into()));
        assert_eq!(p("4 spring onions (65g), cut into diagonal lengths"), (Some(4.0), Some("count".into()), "Spring onions".into()));
    }

    #[test]
    fn real_recipetin_lines_with_nested_notes() {
        assert_eq!(
            p(r#"16  dried chillis (, chopped into 1 cm / 0.5" pieces seeds shaken out (Note 1))"#),
            (Some(16.0), Some("count".into()), "Dried chillis".into())
        );
        assert_eq!(p("2 tbsp lemongrass (, sliced, reedy outer skin removed (1 large) (Note 2))"), (Some(2.0), Some("tbsp".into()), "Lemongrass".into()));
        assert_eq!(p("1 tbsp grated galangal, peeled and grated ((Note 3))"), (Some(1.0), Some("tbsp".into()), "Galangal".into()));
        assert_eq!(unresolved("4  garlic cloves, peeled whole"), (Some("4 cloves".into()), "Garlic".into()));
        assert_eq!(p("1/2 tsp ground coriander"), (Some(0.5), Some("tsp".into()), "Ground coriander".into()));
    }

    #[test]
    fn real_serious_eats_lines() {
        // imperial with metric in brackets: the recipe's own number wins
        let r = parse_ingredient_line("1 quart (1L) homemade or store-bought low-sodium chicken stock");
        assert_eq!((r.amount, r.unit.as_deref()), (Some(1000.0), Some("mL")));
        assert!(r.note.as_deref().unwrap().contains("metric"));
        assert_eq!(p("1/2 pound (225g) finely minced chicken livers"), g(225.0, "Chicken livers"));
        assert_eq!(p("1/4 cup (60ml) extra-virgin olive oil"), (Some(60.0), Some("mL".into()), "Extra-virgin olive oil".into()));
        assert_eq!(p("1 pound (450g) ground beef chuck (about 20% fat)"), g(450.0, "Ground beef chuck"));
        // a can with its size in brackets
        let r = parse_ingredient_line("1 (28-ounce; 800g) can peeled whole tomatoes, preferably San Marzano");
        assert_eq!((r.amount, r.unit.as_deref()), (Some(800.0), Some("g")));
        assert_eq!(r.name, "Peeled whole tomatoes");
    }

    // ---- units ----

    #[test]
    fn metric_and_exact_conversions() {
        assert_eq!(p("100g plain flour"), g(100.0, "Plain flour"));
        assert_eq!(p("1.5kg potatoes"), g(1500.0, "Potatoes"));
        assert_eq!(p("2 kg chicken"), g(2000.0, "Chicken"));
        assert_eq!(p("300ml milk"), (Some(300.0), Some("mL".into()), "Milk".into()));
        assert_eq!(p("1.5 litres water"), (Some(1500.0), Some("mL".into()), "Water".into()));
        assert_eq!(p("4 oz butter"), g(113.0, "Butter"), "oz converts when there are no brackets (to the nearest gram)");
        assert_eq!(p("2 lb mince"), g(907.0, "Mince"));
    }

    #[test]
    fn cups_are_left_blank_with_the_recipes_own_words() {
        assert_eq!(unresolved("2 cups plain flour"), (Some("2 cups".into()), "Plain flour".into()));
        assert_eq!(unresolved("1 1/2 cups milk"), (Some("1 1/2 cups".into()), "Milk".into()));
        assert_eq!(unresolved("½ cup sugar"), (Some("1/2 cup".into()), "Sugar".into()));
        assert_eq!(unresolved("2 fl oz cream"), (Some("2 fl oz".into()), "Cream".into()));
    }

    #[test]
    fn things_with_no_honest_conversion_are_blank_and_flagged() {
        assert_eq!(unresolved("5cm piece of ginger"), (Some("5cm".into()), "Ginger".into()));
        assert_eq!(unresolved("a bunch of fresh coriander"), (Some("a bunch".into()), "Coriander".into()));
        assert_eq!(unresolved("a pinch of salt"), (Some("a pinch".into()), "Salt".into()));
        assert_eq!(unresolved("2 sprigs thyme"), (Some("2 sprigs".into()), "Thyme".into()));
        assert_eq!(unresolved("4 celery stalks, sliced"), (Some("4 stalks".into()), "Celery".into()));
        assert_eq!(unresolved("2 x 400g cans tomatoes"), (Some("2 x 400g cans".into()), "Tomatoes".into()));
        assert_eq!(p("2 tbsp pumpkin seeds").2, "Pumpkin seeds", "a name ending in seeds is not a tail");
    }

    #[test]
    fn counts_and_packs() {
        assert_eq!(p("2 large eggs"), (Some(2.0), Some("count".into()), "Eggs".into()));
        assert_eq!(p("3 onions"), (Some(3.0), Some("count".into()), "Onions".into()));
        assert_eq!(p("1 can coconut milk"), (Some(1.0), Some("count".into()), "Coconut milk".into()));
        assert_eq!(p("2 tins chopped tomatoes"), (Some(2.0), Some("count".into()), "Chopped tomatoes".into()));
        assert_eq!(p("1 can (400g) chickpeas, drained"), g(400.0, "Chickpeas"));
    }

    #[test]
    fn fractions_ranges_and_decimals() {
        assert_eq!(p("1/2 tsp salt").0, Some(0.5));
        assert_eq!(p("1 1/2 tbsp oil").0, Some(1.5));
        assert_eq!(p("2.5 tsp baking powder").0, Some(2.5));
        assert_eq!(p("¾ tsp pepper").0, Some(0.75));
        assert_eq!(p("1 ¼ tsp vanilla").0, Some(1.25));
        let r = parse_ingredient_line("2-3 tbsp lemon juice");
        assert_eq!((r.amount, r.unit.as_deref()), (Some(3.0), Some("tbsp")));
        assert!(r.note.as_deref().unwrap().contains("range"), "a range is flagged: {:?}", r.note);
        assert_eq!(p("2 to 3 cloves garlic").0, None, "cloves stay blank even as a range");
        let r = parse_ingredient_line("1–2 tsp chilli flakes"); // en dash
        assert_eq!(r.amount, Some(2.0));
    }

    // ---- lines with no amount ----

    #[test]
    fn lines_without_an_amount() {
        let r = parse_ingredient_line("groundnut or vegetable oil");
        assert_eq!((r.amount, r.unit, r.unresolved_quantity), (None, None, None));
        assert_eq!(r.name, "Groundnut or vegetable oil");
        assert_eq!(parse_ingredient_line("lemon wedges to serve (optional)").name, "Lemon wedges");
        assert_eq!(parse_ingredient_line("salt and pepper, to taste").name, "Salt and pepper");
        assert_eq!(parse_ingredient_line("Salt").name, "Salt");
    }

    // ---- names ----

    #[test]
    fn names_keep_words_that_make_a_different_product() {
        assert_eq!(p("2 tbsp crushed garlic").2, "Crushed garlic");
        assert_eq!(p("1 tsp dried mint").2, "Dried mint");
        assert_eq!(p("250g frozen spinach").2, "Frozen spinach");
        assert_eq!(p("1 cup whole milk").2, "Whole milk");
        assert_eq!(p("1 tsp freshly ground black pepper").2, "Ground black pepper");
    }

    #[test]
    fn names_lose_size_and_preparation_words() {
        assert_eq!(p("1 large ripe tomato, diced").2, "Tomato");
        assert_eq!(p("2 medium carrots peeled and sliced").2, "Carrots");
        assert_eq!(p("200g butter, softened").2, "Butter");
        assert_eq!(p("1 onion finely chopped").2, "Onion");
        assert_eq!(p("2 tbsp sunflower or vegetable oil plus a little extra for frying").2, "Sunflower or vegetable oil");
    }

    #[test]
    fn html_free_punctuation_and_spacing_is_tidied() {
        assert_eq!(p("  2   tbsp\u{a0}olive   oil  ").2, "Olive oil");
        assert_eq!(parse_ingredient_line("2 tbsp olive oil").raw, "2 tbsp olive oil");
    }

    #[test]
    fn never_panics_on_odd_input() {
        for line in [
            "", " ", "(", ")", "((()))", "1", "1/0 tsp salt", "0 g salt", "/", "-", "½", "1½", "2 x", "2 x 400g",
            "99999999999999999999 g flour", "1.", "1. tsp", "3 - 4", "é 2 tsp", "2 tsp", "g", "tbsp",
        ] {
            let _ = parse_ingredient_line(line);
        }
    }
}
