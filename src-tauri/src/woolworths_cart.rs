//! Woolworths NZ cart automation.
//!
//! Cookie sourcing history worth knowing: the first approach here read
//! session cookies straight out of Chrome/Edge/Firefox's own files on
//! disk (matching v1 — `git show main:kai/core/woolworths_cart.py`).
//! That's abandoned. On Windows, Chrome holds its `Cookies` file with a
//! **fully exclusive lock** while running — confirmed by direct testing,
//! not assumption — which blocks not just a direct SQLite open but even
//! a plain file copy. There's no user-mode workaround short of a Volume
//! Shadow Copy (needs elevation) or closing the browser first.
//!
//! Instead: the app hosts its own login window (a real Tauri webview
//! pointed at Woolworths' real site) and reads the session cookies back
//! from *that* via Tauri's `Webview::cookies_for_url` (Tauri 2.4+, wry
//! 0.47+ — confirmed present at our version, 2.11.5). No external
//! browser file ever touched, no login performed by this code — the
//! user types their own password into Woolworths' own page exactly like
//! any other login, this just reads the resulting cookies back
//! afterward, from the app's own WebView2 profile.
//!
//! Cart-add is `POST /api/v1/trolleys/my/items` with
//! `{"sku", "quantity", "pricingUnit"}` — confirmed working in v1 for
//! `pricingUnit: "Each"`. `"Kg"` for weight-based SKUs is **not**
//! verified against the real API (v1 never sent it — it always used an
//! integer "Each" quantity) — it's a same-pattern extrapolation, not
//! confirmed behavior. Also confirmed directly: the endpoint returns a
//! flat 401 with zero cookies — there's no anonymous/guest cart, an
//! authenticated session is a hard server-side requirement.

use serde::Serialize;

const BASE_URL: &str = "https://www.woolworths.co.nz";
const TROLLEY_ADD_URL: &str = "https://www.woolworths.co.nz/api/v1/trolleys/my/items";
const TROLLEY_URL: &str = "https://www.woolworths.co.nz/api/v1/trolleys/my";
/// The user-facing cart page — confirmed by following the cart link on
/// woolworths.co.nz itself. (`/trolley` is a 404; `/reviewtrolley`
/// redirects to Auth0 login when logged out, which is the expected
/// behavior for a cart page.)
pub const CART_PAGE_URL: &str = "https://www.woolworths.co.nz/reviewtrolley";
const USER_AGENT: &str =
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36";

#[derive(Serialize, Clone, Debug)]
pub struct CartLineResult {
    pub name: String,
    pub sku: String,
    pub quantity: f64,
    pub pricing_unit: String,
    pub ok: bool,
    pub error: Option<String>,
}

#[derive(Serialize, Clone, Debug)]
pub struct CartAddSummary {
    pub results: Vec<CartLineResult>,
}

pub struct CookieJar {
    /// (name, value)
    cookies: Vec<(String, String)>,
}

impl CookieJar {
    pub fn from_cookies(cookies: Vec<(String, String)>) -> Self {
        Self { cookies }
    }

    fn cookie_header(&self) -> String {
        self.cookies
            .iter()
            .map(|(n, v)| format!("{n}={v}"))
            .collect::<Vec<_>>()
            .join("; ")
    }

    fn xsrf_token(&self) -> Option<&str> {
        self.cookies
            .iter()
            .find(|(n, _)| n == "XSRF-TOKEN")
            .map(|(_, v)| v.as_str())
    }
}

/// API calls here must not follow redirects. `reqwest`'s default policy
/// follows up to 10, and a 302 on a POST is replayed as a GET — so a
/// session Woolworths wants to bounce to a login/landing page comes back
/// as whatever *that* page returns (a 404, say) instead of as the
/// redirect it actually was. Refusing to follow keeps the real status
/// and `Location` visible.
fn api_client() -> Result<reqwest::Client, String> {
    reqwest::Client::builder()
        .redirect(reqwest::redirect::Policy::none())
        .build()
        .map_err(|e| format!("Couldn't build HTTP client: {e}"))
}

/// Maps a `/trolleys/my` status onto a login answer, or `None` when the
/// status says nothing about being logged in and should be surfaced as
/// a real error instead.
///
/// Split out because getting this wrong is exactly the bug it was:
/// `check_logged_in` used a flat `status.is_success()`, so *every*
/// non-2xx (a 404, a 500, a redirect landing somewhere odd) reported as
/// "not signed in". That put the cart flow in a loop with no way out —
/// prompt to sign in, user signs in successfully, next check returns
/// the same non-auth failure, prompt again, forever, and nothing on
/// screen ever mentioning the actual status behind it.
fn login_outcome(status: reqwest::StatusCode) -> Option<bool> {
    if status.is_success() {
        Some(true)
    } else if status == reqwest::StatusCode::UNAUTHORIZED
        || status == reqwest::StatusCode::FORBIDDEN
    {
        Some(false)
    } else {
        None
    }
}

/// Ground-truth login check: asks Woolworths whether this session can
/// actually read the user's trolley. `GET /api/v1/trolleys/my` returns
/// 401 with no valid session (confirmed by a zero-cookie request) and
/// 200 with one.
///
/// Deliberately a real request rather than sniffing for known
/// session-cookie names — this used to short-circuit to `false` first
/// when a `CookieJar::is_authenticated()` cookie-name check failed,
/// which was built against v1's Keycloak-era names
/// (`KEYCLOAK_IDENTITY`, `ASP.NET_SessionId`, ...). Woolworths' login is
/// now Auth0-based (`auth.woolworths.co.nz/u/login/...`), which doesn't
/// set any of those — so that pre-check was silently reporting "not
/// logged in" for every real session, before this function ever got to
/// the actual request below. Removed rather than updated with new
/// cookie names: we don't reliably know what Auth0 sets either, and the
/// whole point of this function is to stop guessing from cookie names
/// and ask the API directly.
pub async fn check_logged_in(jar: &CookieJar) -> Result<bool, String> {
    let client = api_client()?;
    let response = client
        .get(TROLLEY_URL)
        .header("User-Agent", USER_AGENT)
        .header("Accept", "application/json, text/plain, */*")
        .header("X-Requested-With", "OnlineShopping.WebApp")
        .header("Referer", format!("{BASE_URL}/"))
        .header("Cookie", jar.cookie_header())
        .send()
        .await
        .map_err(|e| format!("Couldn't reach Woolworths: {e}"))?;

    let status = response.status();
    if let Some(logged_in) = login_outcome(status) {
        return Ok(logged_in);
    }
    Err(format!(
        "Signed in, but Woolworths wouldn't return the trolley: {}. Signing in again won't help — this isn't a sign-in problem. {}",
        status,
        describe_response(response).await
    ))
}

/// Final URL (after any redirects) plus a truncated body — the useful
/// half of a failed response, which the code used to throw away
/// entirely, leaving a bare status code as the only clue.
async fn describe_response(response: reqwest::Response) -> String {
    let url = response.url().to_string();
    let location = response
        .headers()
        .get(reqwest::header::LOCATION)
        .and_then(|v| v.to_str().ok())
        .map(|l| format!(" Redirected to {l}."))
        .unwrap_or_default();
    let body = response.text().await.unwrap_or_default();
    let body = body.trim();
    let snippet: String = body.chars().take(400).collect();
    if snippet.is_empty() {
        format!("(no response body; URL {url}).{location}")
    } else {
        let ellipsis = if body.chars().count() > 400 { "…" } else { "" };
        format!("Response from {url}:{location} {snippet}{ellipsis}")
    }
}

async fn add_item_to_trolley(
    client: &reqwest::Client,
    jar: &CookieJar,
    sku: &str,
    quantity: f64,
    pricing_unit: &str,
) -> Result<bool, String> {
    let mut req = client
        .post(TROLLEY_ADD_URL)
        .header("User-Agent", USER_AGENT)
        .header("Content-Type", "application/json")
        .header("Accept", "application/json, text/plain, */*")
        .header("X-Requested-With", "OnlineShopping.WebApp")
        .header("Origin", BASE_URL)
        .header("Referer", format!("{BASE_URL}/"))
        .header("Cookie", jar.cookie_header());

    if let Some(xsrf) = jar.xsrf_token() {
        req = req.header("X-XSRF-TOKEN", xsrf);
    }

    let response = req
        .json(&serde_json::json!({
            "sku": sku,
            "quantity": quantity,
            "pricingUnit": pricing_unit,
        }))
        .send()
        .await
        .map_err(|e| format!("Request failed: {e}"))?;

    let status = response.status();
    if !status.is_success() {
        // Body included deliberately: a bare "Woolworths returned 404"
        // (what this used to say) gives nothing to act on. Whatever the
        // API says about *why* — an unknown sku, no fulfilment context,
        // an expired session — is in the body, and was being discarded.
        return Err(format!("Woolworths returned {status}. {}", describe_response(response).await));
    }

    let body: serde_json::Value = response
        .json()
        .await
        .map_err(|e| format!("Couldn't parse response: {e}"))?;
    Ok(body.get("isSuccessful").and_then(|v| v.as_bool()).unwrap_or(false))
}

pub struct CartLineInput {
    pub name: String,
    pub sku: String,
    pub quantity: f64,
    pub pricing_unit: String,
}

pub async fn add_all(jar: CookieJar, items: Vec<CartLineInput>) -> Result<CartAddSummary, String> {
    // Real request, not `is_authenticated`'s cookie-name sniffing — same
    // reasoning as `check_logged_in` above. This used to gate on
    // `is_authenticated()` directly, which meant a genuinely successful
    // Auth0 login (no KEYCLOAK_*/ASP.NET_SessionId cookies at all) still
    // got rejected here even though the frontend's own pre-flight check
    // (via `check_logged_in`, same function) had just confirmed the
    // session was good.
    if !check_logged_in(&jar).await? {
        return Err(
            "Not logged in to Woolworths yet — use \"Log in to Woolworths\" first, sign in there, then try again."
                .into(),
        );
    }

    let client = api_client()?;
    let mut results = Vec::with_capacity(items.len());
    for item in items {
        let outcome =
            add_item_to_trolley(&client, &jar, &item.sku, item.quantity, &item.pricing_unit).await;
        results.push(CartLineResult {
            name: item.name,
            sku: item.sku,
            quantity: item.quantity,
            pricing_unit: item.pricing_unit,
            ok: outcome.as_ref().copied().unwrap_or(false),
            error: outcome.err(),
        });
    }

    Ok(CartAddSummary { results })
}

#[cfg(test)]
mod tests {
    use super::*;
    use reqwest::StatusCode;

    /// The reported bug: a 404 from the trolley endpoint was treated as
    /// "not signed in", so signing in (successfully) never cleared the
    /// prompt. Only a real auth rejection may answer `false`.
    #[test]
    fn only_auth_failures_mean_signed_out() {
        assert_eq!(login_outcome(StatusCode::OK), Some(true));
        assert_eq!(login_outcome(StatusCode::NO_CONTENT), Some(true));

        assert_eq!(login_outcome(StatusCode::UNAUTHORIZED), Some(false));
        assert_eq!(login_outcome(StatusCode::FORBIDDEN), Some(false));

        // Everything else is a different problem entirely — surfaced as
        // an error, never as "go sign in again".
        assert_eq!(login_outcome(StatusCode::NOT_FOUND), None);
        assert_eq!(login_outcome(StatusCode::INTERNAL_SERVER_ERROR), None);
        assert_eq!(login_outcome(StatusCode::FOUND), None);
        assert_eq!(login_outcome(StatusCode::TOO_MANY_REQUESTS), None);
    }
}
