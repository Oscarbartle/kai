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
