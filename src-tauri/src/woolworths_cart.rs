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
//! Cart traffic goes through Woolworths' GraphQL API
//! (`POST /api/graphql`), which is what their own site uses. The old
//! REST endpoints this was originally built on
//! (`GET/POST /api/v1/trolleys/my[/items]`) stopped honouring live
//! sessions: confirmed from inside the app with 43 session cookies
//! present (including the chunked `__session__0`/`__session__1` this
//! auth stack sets), that endpoint still answered 401, while
//! `/api/graphql` answered 200 with the same cookies. Note their site
//! no longer sets `XSRF-TOKEN` at all, which the REST call used to send.
//!
//! The two operations used here, both taken from woolworths.co.nz's own
//! bundles rather than guessed:
//!   - `query GetMeProfile { me { id } }` — the login check. Answers 200
//!     either way, so the body is the signal: a guest gets
//!     "Field 'me' is not allowed for guest users." (BANNED_OPERATION).
//!   - `mutation SetCartLineItemQuantity($input: SetCartLineItemQuantitiesInput!)`
//!     — the cart write, taking
//!     `cartLineItemQuantityUpdates: [{ variantKey, quantity }]`. It
//!     *sets* a quantity rather than adding to it, exactly like the old
//!     REST call did, so the merge-before-round logic in `commands.rs`
//!     is unaffected.
//!
//! `variantKey` replaces the old `sku` + `pricingUnit` pair and is
//! `{stock code}-EA` / `{stock code}-KG` — see `variant_key`.
//!
//! Product lookup (`woolworths.rs`) is a separate REST API and is
//! unaffected — still returns 200.

use serde::Serialize;

const BASE_URL: &str = "https://www.woolworths.co.nz";
const TROLLEY_URL: &str = "https://www.woolworths.co.nz/api/v1/trolleys/my";
/// Where Woolworths' own site now sends its cart traffic (confirmed by
/// watching woolworths.co.nz: `POST /api/graphql?op-name=CustomerCart`).
const GRAPHQL_URL: &str = "https://www.woolworths.co.nz/api/graphql";
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
    let value = graphql(
        &client,
        jar,
        "GetMeProfile",
        "query GetMeProfile { me { id } }",
        serde_json::json!({}),
    )
    .await?;

    if value
        .get("data")
        .and_then(|d| d.get("me"))
        .and_then(|m| m.get("id"))
        .is_some()
    {
        return Ok(true);
    }

    // Guests get a specific, documented refusal rather than an HTTP
    // error — the endpoint answers 200 either way, so the *body* is the
    // only signal. Confirmed against the live API while signed out:
    //   "Field 'me' is not allowed for guest users."  (BANNED_OPERATION)
    let errors = graphql_error_text(&value);
    if errors.contains("not allowed for guest")
        || errors.contains("BANNED_OPERATION")
        || errors.contains("UNAUTHENTICATED")
    {
        return Ok(false);
    }

    Err(format!(
        "Couldn't tell whether you're signed in to Woolworths. {}",
        if errors.is_empty() { value.to_string() } else { errors }
    ))
}

/// `{stock code}-EA` / `{stock code}-KG` — how the new API addresses a
/// specific purchasable variant, replacing the old `sku` + `pricingUnit`
/// pair. Verified against real products: an each-only line like diced
/// tomatoes (311488) exposes only `311488-EA`, while a weight-capable
/// one like loose onions (144329) or chicken thighs (57005) exposes both
/// `-KG` and `-EA` — which is the same dual-mode idea the SKU model
/// already carries as `supports_both_each_and_kg`.
fn variant_key(sku: &str, pricing_unit: &str) -> String {
    let suffix = if pricing_unit.eq_ignore_ascii_case("kg") { "KG" } else { "EA" };
    format!("{sku}-{suffix}")
}

/// Collapses a GraphQL response's `errors[]` into one string. GraphQL
/// answers 200 with errors in the body, so status alone says nothing.
fn graphql_error_text(value: &serde_json::Value) -> String {
    value
        .get("errors")
        .and_then(|e| e.as_array())
        .map(|arr| {
            arr.iter()
                .filter_map(|e| e.get("message").and_then(|m| m.as_str()))
                .collect::<Vec<_>>()
                .join("; ")
        })
        .unwrap_or_default()
}

/// One POST to Woolworths' GraphQL endpoint, carrying the app's own
/// session cookies. `op-name` goes in the query string the same way
/// their site sends it.
async fn graphql(
    client: &reqwest::Client,
    jar: &CookieJar,
    op_name: &str,
    query: &str,
    variables: serde_json::Value,
) -> Result<serde_json::Value, String> {
    let response = client
        .post(format!("{GRAPHQL_URL}?op-name={op_name}"))
        .header("User-Agent", USER_AGENT)
        .header("Content-Type", "application/json")
        .header("Accept", "application/json, text/plain, */*")
        .header("Origin", BASE_URL)
        .header("Referer", format!("{BASE_URL}/"))
        .header("Cookie", jar.cookie_header())
        .json(&serde_json::json!({
            "operationName": op_name,
            "variables": variables,
            "query": query,
        }))
        .send()
        .await
        .map_err(|e| format!("Couldn't reach Woolworths: {e}"))?;

    let status = response.status();
    if !status.is_success() {
        return Err(format!("Woolworths returned {status}. {}", describe_response(response).await));
    }
    response
        .json()
        .await
        .map_err(|e| format!("Couldn't parse Woolworths' response: {e}"))
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

/// One-click diagnosis for "the webview is signed in but our request
/// isn't". Reports what the cookie jar actually contains (names only —
/// never values, these are live session credentials), then what both
/// the legacy REST trolley endpoint and the GraphQL endpoint their site
/// now uses actually say back.
///
/// Exists because "Not signed in" alone can't distinguish the two
/// causes, which need opposite fixes: either we're reading the wrong
/// cookies (a bug here), or the session is fine and the REST API itself
/// no longer honours it (an upstream change we have to re-target).
pub async fn session_debug(jar: &CookieJar) -> String {
    let mut out = String::new();

    let names: Vec<&str> = jar.cookies.iter().map(|(n, _)| n.as_str()).collect();
    out.push_str(&format!("Cookies visible to Kai for www.woolworths.co.nz: {}
", names.len()));
    if names.is_empty() {
        out.push_str("  (none — the session cookies aren't reaching this window at all)
");
    } else {
        out.push_str(&format!("  {}
", names.join(", ")));
    }
    out.push_str(&format!("  XSRF-TOKEN present: {}

", jar.xsrf_token().is_some()));

    let client = match api_client() {
        Ok(c) => c,
        Err(e) => return format!("{out}Couldn't build HTTP client: {e}"),
    };

    // Legacy REST endpoint the cart-add is currently built on.
    out.push_str("GET /api/v1/trolleys/my (what Kai uses today):
");
    match client
        .get(TROLLEY_URL)
        .header("User-Agent", USER_AGENT)
        .header("Accept", "application/json, text/plain, */*")
        .header("X-Requested-With", "OnlineShopping.WebApp")
        .header("Referer", format!("{BASE_URL}/"))
        .header("Cookie", jar.cookie_header())
        .send()
        .await
    {
        Ok(r) => {
            let status = r.status();
            out.push_str(&format!("  {status}. {}

", describe_response(r).await));
        }
        Err(e) => out.push_str(&format!("  request failed: {e}

")),
    }

    // The GraphQL endpoint their own site now calls for the cart.
    out.push_str("POST /api/graphql (what their site now uses):
");
    match client
        .post(GRAPHQL_URL)
        .header("User-Agent", USER_AGENT)
        .header("Content-Type", "application/json")
        .header("Accept", "application/json, text/plain, */*")
        .header("Origin", BASE_URL)
        .header("Referer", format!("{BASE_URL}/"))
        .header("Cookie", jar.cookie_header())
        .json(&serde_json::json!({
            "operationName": "KaiProbe",
            "variables": {},
            "query": "query KaiProbe { __typename }",
        }))
        .send()
        .await
    {
        Ok(r) => {
            let status = r.status();
            out.push_str(&format!("  {status}. {}
", describe_response(r).await));
        }
        Err(e) => out.push_str(&format!("  request failed: {e}
")),
    }

    out
}

/// Sets a variant's quantity in the cart via the mutation their own
/// site uses. Note *set*, not add — which is what the previous REST
/// call did too, so the existing merge-before-round logic in
/// `commands.rs` stays exactly as correct as it was.
async fn set_cart_line_quantity(
    client: &reqwest::Client,
    jar: &CookieJar,
    sku: &str,
    quantity: f64,
    pricing_unit: &str,
) -> Result<bool, String> {
    let value = graphql(
        client,
        jar,
        "SetCartLineItemQuantity",
        "mutation SetCartLineItemQuantity($input: SetCartLineItemQuantitiesInput!) {            setCartLineItemQuantity(input: $input) { __typename }          }",
        serde_json::json!({
            "input": {
                "cartLineItemQuantityUpdates": [{
                    "variantKey": variant_key(sku, pricing_unit),
                    "quantity": quantity,
                }]
            }
        }),
    )
    .await?;

    let errors = graphql_error_text(&value);
    if !errors.is_empty() {
        return Err(errors);
    }
    Ok(value
        .get("data")
        .and_then(|d| d.get("setCartLineItemQuantity"))
        .is_some())
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
            set_cart_line_quantity(&client, &jar, &item.sku, item.quantity, &item.pricing_unit).await;
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
