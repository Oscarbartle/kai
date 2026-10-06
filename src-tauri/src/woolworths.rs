//! Read-only Woolworths NZ product lookup.
//!
//! Public, unauthenticated endpoint — reverse-engineered from browser
//! devtools, see CLAUDE.md for the full notes. Runs on the Rust side
//! because the API doesn't send CORS headers, so the webview can't call
//! it directly from the frontend.

// Sku/SkuPrice/SkuSize/SkuQuantity moved to kai-shared (Phase B: these are
// the wire shapes a future remote server needs to produce too, not just
// this local fetch — see crates/kai-shared/src/skus.rs).
pub use kai_shared::skus::{Sku, SkuPrice, SkuQuantity, SkuSize};

const BASE_URL: &str = "https://www.woolworths.co.nz";

/// Accepts either a bare stock code ("705692") or a pasted product URL
/// (".../shop/productdetails?stockcode=705692&name=...") and pulls the
/// numeric stock code out of either.
fn extract_stock_code(input: &str) -> Result<String, String> {
    let trimmed = input.trim();

    if let Some(idx) = trimmed.find("stockcode=") {
        let after = &trimmed[idx + "stockcode=".len()..];
        let code: String = after.chars().take_while(|c| c.is_ascii_digit()).collect();
        if !code.is_empty() {
            return Ok(code);
        }
    }

    let digits: String = trimmed.chars().filter(|c| c.is_ascii_digit()).collect();
    if digits.is_empty() {
        return Err("Couldn't find a stock code in that — paste a Woolworths product URL or just the stock code number.".into());
    }
    Ok(digits)
}

#[tauri::command]
pub async fn fetch_woolworths_sku(input: String) -> Result<Sku, String> {
    let stock_code = extract_stock_code(&input)?;
    let url = format!("{BASE_URL}/api/v1/products/{stock_code}");

    let client = reqwest::Client::new();
    let response = client
        .get(&url)
        .header("User-Agent", "Mozilla/5.0")
        .header("X-Requested-With", "XMLHttpRequest")
        .send()
        .await
        .map_err(|e| format!("Request failed: {e}"))?;

    if !response.status().is_success() {
        return Err(format!(
            "Woolworths returned {} for stock code {stock_code}",
            response.status()
        ));
    }

    let raw: serde_json::Value = response
        .json()
        .await
        .map_err(|e| format!("Couldn't parse response: {e}"))?;

    parse_sku(&stock_code, &raw)
}

fn parse_sku(stock_code: &str, raw: &serde_json::Value) -> Result<Sku, String> {
    let name = raw
        .get("name")
        .and_then(|v| v.as_str())
        .unwrap_or_default()
        .to_string();
    if name.is_empty() {
        return Err(format!("No product found for stock code {stock_code}"));
    }

    let price = raw.get("price").cloned().unwrap_or_default();
    let size = raw.get("size").cloned().unwrap_or_default();
    let quantity = raw.get("quantity").cloned().unwrap_or_default();

    let images = raw
        .get("images")
        .and_then(|v| v.as_array())
        .map(|arr| {
            arr.iter()
                .filter_map(|img| img.get("big").and_then(|b| b.as_str()).map(str::to_string))
                .collect()
        })
        .unwrap_or_default();

    let allergens = raw
        .get("allergens")
        .and_then(|v| v.as_array())
        .map(|arr| arr.iter().filter_map(|v| v.as_str().map(str::to_string)).collect())
        .unwrap_or_default();

    let ingredients = raw
        .get("ingredients")
        .and_then(|v| v.get("ingredients"))
        .and_then(|v| v.as_array())
        .map(|arr| arr.iter().filter_map(|v| v.as_str().map(str::to_string)).collect())
        .unwrap_or_default();

    let stock_level = raw
        .get("stockLevel")
        .and_then(|v| v.as_i64())
        .or_else(|| raw.get("productStoresStockLevel").and_then(|v| v.as_i64()));

    let availability_status = raw
        .get("availabilityStatus")
        .and_then(|v| v.as_str())
        .map(str::to_string);

    Ok(Sku {
        provider: "woolworths".to_string(),
        sku: stock_code.to_string(),
        name,
        brand: raw.get("brand").and_then(|v| v.as_str()).map(str::to_string),
        variety: raw.get("variety").and_then(|v| v.as_str()).map(str::to_string),
        price: SkuPrice {
            original_price: price.get("originalPrice").and_then(|v| v.as_f64()),
            sale_price: price.get("salePrice").and_then(|v| v.as_f64()),
            is_special: price.get("isSpecial").and_then(|v| v.as_bool()).unwrap_or(false),
            save_percentage: price.get("savePercentage").and_then(|v| v.as_f64()),
            promotion_start_date: price
                .get("promotionStartDate")
                .and_then(|v| v.as_str())
                .map(str::to_string),
            promotion_end_date: price
                .get("promotionEndDate")
                .and_then(|v| v.as_str())
                .map(str::to_string),
        },
        size: SkuSize {
            cup_price: size.get("cupPrice").and_then(|v| v.as_f64()),
            cup_measure: size.get("cupMeasure").and_then(|v| v.as_str()).map(str::to_string),
            package_type: size.get("packageType").and_then(|v| v.as_str()).map(str::to_string),
            volume_size: size.get("volumeSize").and_then(|v| v.as_str()).map(str::to_string),
        },
        quantity: SkuQuantity {
            unit: raw
                .get("unit")
                .and_then(|v| v.as_str())
                .unwrap_or("Each")
                .to_string(),
            min: quantity.get("min").and_then(|v| v.as_f64()),
            max: quantity.get("max").and_then(|v| v.as_f64()),
            increment: quantity.get("increment").and_then(|v| v.as_f64()),
            supports_both_each_and_kg: raw
                .get("supportsBothEachAndKgPricing")
                .and_then(|v| v.as_bool())
                .unwrap_or(false),
            // API sends 0.0 rather than omitting the field when not
            // applicable — treat that as "no value" like everything else.
            average_weight_per_unit: raw
                .get("averageWeightPerUnit")
                .and_then(|v| v.as_f64())
                .filter(|v| *v > 0.0),
        },
        availability_status,
        stock_level,
        images,
        allergens,
        ingredients,
    })
}

// ------------------------------------------------------------------ search

/// One product in a search result: enough to recognise it and compare
/// prices. The full record (allergens, ingredients, every image) comes from
/// [`fetch_woolworths_sku`] once a product is actually chosen — the search
/// endpoint doesn't carry them.
#[derive(serde::Serialize, Clone, Debug, PartialEq)]
pub struct ProductHit {
    pub sku: String,
    pub name: String,
    pub brand: Option<String>,
    pub variety: Option<String>,
    pub volume_size: Option<String>,
    pub package_type: Option<String>,
    pub sale_price: Option<f64>,
    pub original_price: Option<f64>,
    pub is_special: bool,
    pub cup_price: Option<f64>,
    pub cup_measure: Option<String>,
    pub unit: Option<String>,
    pub availability: Option<String>,
    pub image_url: Option<String>,
}

fn text(v: Option<&serde_json::Value>) -> Option<String> {
    v.and_then(|v| v.as_str())
        .map(str::trim)
        .filter(|s| !s.is_empty())
        .map(str::to_string)
}

/// Search results mix real products with advert tiles
/// (`"type": "PromoTile"`, no SKU, a campaign name for a title) — only
/// products with a SKU are kept. Anything else about the shape being off
/// gives fewer hits, never an error: a search that finds nothing is a
/// normal answer.
fn parse_search_results(raw: &serde_json::Value) -> Vec<ProductHit> {
    let Some(items) = raw.pointer("/products/items").and_then(|v| v.as_array()) else {
        return Vec::new();
    };
    items
        .iter()
        .filter(|item| item.get("type").and_then(|t| t.as_str()).map_or(true, |t| t == "Product"))
        .filter_map(|item| {
            let sku = match item.get("sku")? {
                serde_json::Value::String(s) if !s.trim().is_empty() => s.trim().to_string(),
                serde_json::Value::Number(n) => n.to_string(),
                _ => return None,
            };
            let name = text(item.get("name"))?;
            let price = item.get("price");
            let size = item.get("size");
            // `images` is {small, big} here but a list of those on the
            // detail endpoint; accept both.
            let image_url = match item.get("images") {
                Some(obj) if obj.is_object() => text(obj.get("big")).or_else(|| text(obj.get("small"))),
                Some(arr) if arr.is_array() => arr
                    .as_array()
                    .and_then(|a| a.first())
                    .and_then(|first| text(first.get("big")).or_else(|| text(first.get("small")))),
                _ => None,
            };
            Some(ProductHit {
                sku,
                name,
                brand: text(item.get("brand")),
                variety: text(item.get("variety")),
                volume_size: text(size.and_then(|s| s.get("volumeSize"))),
                package_type: text(size.and_then(|s| s.get("packageType"))),
                sale_price: price.and_then(|p| p.get("salePrice")).and_then(|v| v.as_f64()),
                original_price: price.and_then(|p| p.get("originalPrice")).and_then(|v| v.as_f64()),
                is_special: price.and_then(|p| p.get("isSpecial")).and_then(|v| v.as_bool()).unwrap_or(false),
                cup_price: size.and_then(|s| s.get("cupPrice")).and_then(|v| v.as_f64()),
                cup_measure: text(size.and_then(|s| s.get("cupMeasure"))),
                unit: text(item.get("unit")),
                availability: text(item.get("availabilityStatus")),
                image_url,
            })
        })
        .collect()
}

/// Free-text product search, for finding the SKU of a new item. Same public
/// endpoint family as the product lookup above (and the same header it
/// needs — without one the API answers 400).
#[tauri::command]
pub async fn search_woolworths(query: String) -> Result<Vec<ProductHit>, String> {
    let query = query.trim();
    if query.is_empty() {
        return Err("Type something to search for".to_string());
    }
    if query.chars().count() > 100 {
        return Err("That search is too long".to_string());
    }

    let client = reqwest::Client::builder()
        .timeout(std::time::Duration::from_secs(20))
        .build()
        .map_err(|e| format!("Couldn't start the search: {e}"))?;
    let response = client
        .get(format!("{BASE_URL}/api/v1/products"))
        .query(&[
            ("target", "search"),
            ("search", query),
            ("inStockProductsOnly", "false"),
            ("size", "12"),
        ])
        .header("User-Agent", "Mozilla/5.0")
        .header("X-Requested-With", "XMLHttpRequest")
        .send()
        .await
        .map_err(|e| format!("Couldn't reach Woolworths: {e}"))?;

    if !response.status().is_success() {
        return Err(format!("Woolworths answered the search with {}", response.status()));
    }
    let raw: serde_json::Value = response
        .json()
        .await
        .map_err(|e| format!("Couldn't read Woolworths' answer: {e}"))?;
    Ok(parse_search_results(&raw))
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    /// Trimmed from a real `search=soy sauce` answer (2026-10-06): note the
    /// advert tile in the middle, lowercase names, `images` as an object.
    fn real_shaped() -> serde_json::Value {
        json!({"products": {"totalItems": 34, "items": [
            {"type": "Product", "sku": "270415", "name": "highmark soy sauce golden", "brand": "highmark",
             "variety": "golden", "unit": "Each", "availabilityStatus": "In Stock",
             "price": {"originalPrice": 4.1, "salePrice": 4.1, "isSpecial": false},
             "size": {"volumeSize": "550mL", "packageType": null, "cupPrice": 0.75, "cupMeasure": "100mL"},
             "images": {"small": "https://img/270415-s.jpg", "big": "https://img/270415-b.jpg"}},
            {"type": "PromoTile", "sku": null, "name": "Cartology-Default Content-Search CIG", "images": []},
            {"type": "Product", "sku": "198763", "name": "lee kum kee soy sauce premium", "brand": "lee kum kee",
             "variety": "premium", "unit": "Each", "availabilityStatus": "In Stock",
             "price": {"originalPrice": 5.79, "salePrice": 5.0, "isSpecial": true},
             "size": {"volumeSize": "500mL", "cupPrice": 1.0, "cupMeasure": "100mL"},
             "images": {"small": "https://img/198763-s.jpg"}}
        ]}})
    }

    #[test]
    fn keeps_products_and_drops_advert_tiles() {
        let hits = parse_search_results(&real_shaped());
        assert_eq!(hits.iter().map(|h| h.sku.as_str()).collect::<Vec<_>>(), ["270415", "198763"]);
        let first = &hits[0];
        assert_eq!(first.name, "highmark soy sauce golden");
        assert_eq!((first.brand.as_deref(), first.variety.as_deref()), (Some("highmark"), Some("golden")));
        assert_eq!((first.sale_price, first.original_price, first.is_special), (Some(4.1), Some(4.1), false));
        assert_eq!(
            (first.volume_size.as_deref(), first.cup_price, first.cup_measure.as_deref()),
            (Some("550mL"), Some(0.75), Some("100mL"))
        );
        assert_eq!(first.image_url.as_deref(), Some("https://img/270415-b.jpg"), "the big image when there is one");
        assert_eq!(first.availability.as_deref(), Some("In Stock"));
        let special = &hits[1];
        assert!(special.is_special && special.sale_price < special.original_price);
        assert_eq!(special.image_url.as_deref(), Some("https://img/198763-s.jpg"), "falls back to the small one");
    }

    #[test]
    fn an_answer_with_nothing_useful_is_an_empty_list_not_an_error() {
        // what a nonsense query really returns: just an advert tile
        let only_tile = json!({"products": {"items": [{"type": "PromoTile", "sku": null, "name": "Ad"}]}});
        assert!(parse_search_results(&only_tile).is_empty());
        assert!(parse_search_results(&json!({"products": {"items": []}})).is_empty());
        assert!(parse_search_results(&json!({"products": {}})).is_empty());
        assert!(parse_search_results(&json!({})).is_empty());
        assert!(parse_search_results(&json!(null)).is_empty());
    }

    #[test]
    fn odd_products_are_handled_not_trusted() {
        let raw = json!({"products": {"items": [
            {"sku": 123456, "name": "numeric sku, no type"},
            {"type": "Product", "sku": "", "name": "blank sku"},
            {"type": "Product", "sku": "777", "name": "   "},
            {"type": "Product", "sku": "888", "name": "no price or size or images"},
            {"type": "Product", "sku": "999", "name": "list-style images", "images": [{"big": "https://img/b.jpg"}]}
        ]}});
        let hits = parse_search_results(&raw);
        assert_eq!(hits.iter().map(|h| h.sku.as_str()).collect::<Vec<_>>(), ["123456", "888", "999"]);
        assert_eq!(hits[1].sale_price, None);
        assert!(!hits[1].is_special);
        assert_eq!(hits[1].image_url, None);
        assert_eq!(hits[2].image_url.as_deref(), Some("https://img/b.jpg"));
    }

    #[tokio::test]
    async fn empty_and_overlong_queries_are_refused_before_any_request() {
        assert!(search_woolworths("   ".into()).await.unwrap_err().contains("Type something"));
        assert!(search_woolworths("x".repeat(101)).await.unwrap_err().contains("too long"));
    }

    #[tokio::test]
    #[ignore = "hits the real Woolworths site"]
    async fn live_search_finds_real_products() {
        let hits = search_woolworths("soy sauce".into()).await.expect("search");
        assert!(!hits.is_empty(), "soy sauce should find products");
        for h in &hits {
            println!("{:8} {:<40} {:?} {:?} ${:?}", h.sku, h.name, h.brand, h.volume_size, h.sale_price);
        }
        assert!(hits.iter().all(|h| !h.sku.is_empty() && !h.name.is_empty()));
        let none = search_woolworths("zzqxkvbnm".into()).await.expect("search");
        assert!(none.is_empty(), "a nonsense word finds nothing, not an error: {none:?}");
    }
}
