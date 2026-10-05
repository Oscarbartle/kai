# Kai

Personal grocery/recipe app. Currently mid-rewrite (v2) from a Python/PySide6
desktop app into a Tauri + Svelte + TypeScript app with a Rust backend.

## Working style (Oscar's preferences)

- **Go slow, one piece at a time.** Build the smallest working slice, confirm
  it, then move on. Don't jump ahead to the next feature unprompted.
- **Talk through concepts before writing code** for anything non-trivial —
  data models especially. Ask clarifying questions, converge on a shape, then
  implement.
- **No example/template cruft.** When scaffolding tools drop in boilerplate
  (demo pages, unused example assets, starter logos), strip it immediately
  rather than leaving it "for now."
- **Ground decisions in real data/behavior, not assumptions** — e.g. query the
  actual API and look at the actual response before designing a model around
  it. This has repeatedly surfaced things a spec/assumption would have missed
  (see the `supportsBothEachAndKgPricing` note below).
- Confirm scope before broad or destructive actions (wiping files, deleting
  branches, etc.) even when the direction has been agreed in principle.

## Project state

- `main` — the old Python/PySide6 app, full history preserved, not being
  developed further. Reference it for prior art (see below) but don't build
  on it.
- `v2` — active branch. Tauri + Svelte + TS shell with a working SQLite-backed
  Item/SKU/tag/Recipe system (see below) — a functional slice, not just
  scaffolding. UI is intentionally minimal/undesigned so far ("build the
  functions, style it later" — explicit call, not neglect).

## Architecture direction

- **Frontend**: Svelte + TypeScript (chosen for being lightweight, low
  boilerplate, common Tauri pairing). `/app` is the whole app now — the
  Tauri window loads it directly (`tauri.conf.json`'s window `url`); `/`
  is just a client-side redirect there, for anyone who loads the raw dev
  server root in a browser. Started as flat single-file pages per
  section (`/items`, `/recipes`, `/shopping-list`, exercising backend
  commands directly, no shared components) before being replaced piece
  by piece with `/app`'s tabbed Pantry/Recipe Book/Shopping Lists UI —
  those old pages are gone now that `/app` fully covers what they did.
- **Backend**: Rust, via Tauri commands (`#[tauri::command]`) — rewriting the
  old Python logic rather than porting it as-is.
- **Storage**: SQLite via `rusqlite` (bundled) + `rusqlite_migration`. DB file
  lives in the Tauri app-data dir (`kai.db`, resolved via
  `app.path().app_data_dir()`). All access goes through repository modules
  (`src-tauri/src/db/{items,skus,tags,recipes,recipe_items}.rs`) — Tauri
  commands (`commands.rs`) never touch raw SQL. Chosen over `sqlx` deliberately: `sqlx`'s main
  benefit (SQL portability to Postgres) doesn't actually apply here, since
  a future remote mode would go through an API service (see below), not a
  direct Postgres connection from the client — so the repository-module
  boundary is what protects the future move, not the DB crate. Migrations
  are plain SQL, appended-only (never edit an already-shipped migration).
- **Cross-platform**: macOS + Windows desktop first. Windows builds need a
  Windows machine or CI (can't cross-compile from macOS). Android is possible
  later via Tauri 2.0 mobile support but needs its own init + touch UI work —
  not started.
- **Phone companion — in progress** (was a "future idea" for a second
  Tauri app under `apps/mobile`). Became a small installable web app in
  `mobile/`, served by `kai-server` itself — see "Mobile web app" below
  for why that beat a second Tauri app.
- **Auto-update — implemented.** `tauri-plugin-updater` + `tauri-plugin-process`,
  wired into a new "Updates" section in `Settings.svelte`: checks
  silently on open, shows a version/notes + "Install & restart" button
  if one's found, falls back to a plain "Check again" otherwise. Point
  of building this at all — Oscar's partner isn't expected to know what
  a GitHub release is, so a new version has to surface *inside the app*.
  - **Hosting: GitHub Releases**, decided over self-hosting on the
    Unraid box once the `kai` repo went public — a public repo's release
    assets are plain HTTPS URLs, no auth/token needed by the updater, no
    new server to run. (Self-hosting was the fallback if the repo had to
    stay private — a private repo's release assets require an auth
    token to fetch, which the updater can't do without embedding a
    secret in the shipped app.)
  - **Signing**: a minisign keypair generated via `tauri signer generate`,
    private key + password stored *outside* the repo
    (`~/.tauri/kai-updater.key`, never committed) and as the
    `TAURI_SIGNING_PRIVATE_KEY`/`TAURI_SIGNING_PRIVATE_KEY_PASSWORD`
    GitHub Actions secrets on the repo; the public key lives in
    `tauri.conf.json`'s `plugins.updater.pubkey`. Losing the private key
    means no future update can ever be verified by installs signed with
    the old public key — there's no recovery, only shipping a new
    keypair and having everyone reinstall from scratch.
  - **Release pipeline**: `.github/workflows/release.yml`, triggered by
    pushing a `v*.*.*` tag (or manual dispatch). Uses the official
    `tauri-apps/tauri-action` to build the Windows installer, sign the
    updater artifacts (`bundle.createUpdaterArtifacts: true` in
    `tauri.conf.json` is what makes those artifacts exist at all), and
    publish a GitHub Release with the `latest.json` manifest the
    updater's `endpoints` config polls
    (`.../releases/latest/download/latest.json`). Deliberately
    **`releaseDraft: true`** — a build finishing doesn't mean it goes
    out to Oscar's partner; the release sits as a draft (invisible to
    "latest") until someone manually publishes it on GitHub, a
    last-look safety gate before a real person's app auto-updates.
  - **No macOS build wired up yet** — Windows only, matching "Windows
    first" above. The workflow runs on `windows-latest` only.
  - Version bump is manual and three-places: `package.json`,
    `src-tauri/Cargo.toml`, and `src-tauri/tauri.conf.json` all need the
    same version before tagging a release, or the app's own reported
    version (Settings' "Currently running version …") won't match what
    was actually tagged/built.
- **Multi-retailer**: Woolworths NZ only for now, but model things so another
  supermarket can be added later via a settings/provider switch rather than
  hardcoding Woolworths assumptions everywhere. SKU rows already carry a
  `provider` column for this.
- **Remote mode**: an API service on the Unraid box backed by Postgres —
  mirroring the old v1 `kai/server/` pattern — with the desktop client
  talking to it over HTTP instead of a direct Postgres connection. Done
  and deployed — see "Phase B: shared remote database" below.
- **Woolworths migrated their cart to GraphQL (2026-08-31) — REST cart
  API retired.** Symptom was an inescapable loop: sign in successfully,
  app still says "not signed in", cart-add 404s. Root cause is upstream,
  not ours — nothing in the cookie-reading path had changed since the
  release where it worked. Confirmed from inside the app: 43 session
  cookies visible (including the chunked `__session__0`/`__session__1`
  this auth stack sets, and *no* `XSRF-TOKEN` any more), yet
  `GET /api/v1/trolleys/my` still answered 401 while `POST /api/graphql`
  answered 200 with those same cookies.
  - Cart now goes through `POST /api/graphql` (what woolworths.co.nz
    itself calls). Operations lifted from their own JS bundles, not
    guessed:
    - Login check: `query GetMeProfile { me { id } }`. Answers HTTP 200
      either way — the *body* is the signal, a guest gets
      `"Field 'me' is not allowed for guest users."` (BANNED_OPERATION).
    - Cart write: `mutation SetCartLineItemQuantity($input:
      SetCartLineItemQuantitiesInput!)`, taking
      `cartLineItemQuantityUpdates: [{ variantKey, quantity }]`. Still
      *sets* rather than adds, exactly like the old REST call, so the
      merge-before-round logic in `commands.rs` is unaffected.
  - **`variantKey` replaces `sku` + `pricingUnit`**: `{stock code}-EA` /
    `{stock code}-KG`. Verified against real pantry SKUs — each-only
    items (diced tomatoes 311488, colby 281810, pasta 727848) expose
    only `-EA`, weight-capable ones (onions 144329, chicken thighs
    57005) expose both. That's the same dual-mode idea already stored as
    `supports_both_each_and_kg`.
  - Introspection is disabled, but **validation errors leak input types**
    — sending a wrong field returned the full
    `input CartLineItemQuantitySetInput { variantKey: String! quantity:
    Decimal! advertisementId: String }`. That's how the shape above was
    established rather than guessed.
  - Verified as far as an unauthenticated session allows: the real
    mutation with real variables passes validation and fails *only* with
    `"The operation 'setCartLineItemQuantity' is banned for cart type
    'GuestCart'"` — shape correct, auth the only difference.
  - **The cart page URL moved too**: `/reviewtrolley` now returns a real
    404 (that's the page the app opened after a successful add). It's
    `/cart` now — read off the cart control on their own site. Telling a
    live route from a dead one needs care since their SPA answers 200 for
    almost anything; the tell is that `/cart` redirects a signed-out
    visitor to Auth0 login (what a real cart page does) while
    `/reviewtrolley`, `/trolley`, `/shop/cart` and `/basket` all answer an
    actual 404.
  - **Product lookup is a separate REST API and is unaffected** —
    `/api/v1/products/{sku}` still returns 200, so Pantry, SKU add and
    price refresh keep working. Only the cart features broke.
  - Settings → Woolworths account has a **Diagnose** button
    (`woolworths_session_debug`) reporting visible cookie *names* (never
    values), and what both endpoints actually answer — built because
    "Not signed in" alone couldn't distinguish "wrong cookies" from
    "endpoint retired", which need opposite fixes.

- **Woolworths cart interaction — implemented** *(partly superseded: the
  GraphQL migration note above replaces the retired REST cart API this
  section describes — the cart-add request, the login-check request and
  the `/reviewtrolley` URL below are all out of date. The app-hosted login
  window, the cookie reading, and the merge-before-round / multi-list
  logic still hold.)* (`src-tauri/src/woolworths_cart.rs`,
  originally wired to a plain "Log in to Woolworths" + "Add all to
  Woolworths cart" button pair on the old flat `/shopping-list` page,
  now `Settings.svelte`'s account section + `CartAdd.svelte` in `/app` —
  see both below). Cart-add is `POST /api/v1/trolleys/my/items`
  with `{"sku", "quantity", "pricingUnit"}` — the request shape is confirmed
  from v1's already-working code (`git show main:kai/core/woolworths_cart.py`)
  for `pricingUnit: "Each"`. **`"Kg"` for weight-based SKUs is a same-pattern
  extrapolation, not verified against the real API** — v1 never sent it.
  Also confirmed directly (curl, zero cookies): the endpoint hard-401s with
  no anonymous/guest-cart path at all — an authenticated session is a
  server-side requirement, not something we could route around.
  - **Auth: the app hosts its own login window**, not v1's approach. The
    original plan (and v1's actual mechanism) was reading session cookies
    straight out of the user's real browser's files on disk. That was
    built, then abandoned after real testing: on Windows, Chrome holds its
    `Cookies` file with a **fully exclusive lock** while running — not just
    blocking a direct SQLite open, but blocking even a plain file copy
    (confirmed via `ERROR_SHARING_VIOLATION`, not assumed). No user-mode
    workaround exists short of a Volume Shadow Copy (needs elevation) or
    closing the browser first — which is what a well-regarded purpose-built
    Chrome-cookie-decryption tool actually does. Instead, `open_woolworths_login`
    opens a real Tauri window; the user logs in there directly (password
    goes into Woolworths' own page, never touched by this code);
    `add_shopping_list_to_cart` reads the resulting session back via
    Tauri's `Webview::cookies_for_url` (needs Tauri 2.4+ — we're on
    2.11.5). No external browser file involved at all, so the Windows
    locking problem doesn't apply. Confirmed synchronous at our version
    (not async, despite older docs suggesting otherwise) — safe to call
    from an `async fn` command since Tauri runs those off the main thread,
    which is what the "don't call this synchronously, it can deadlock on
    Windows" warning is actually about.
  - **Login window opens straight to the sign-in form, not the
    homepage.** Woolworths' own "Sign In" button isn't a link — it calls
    `GET /api/v1/bff/initiate-oidc-signin?op=login&redirectUrl=…`, which
    mints a fresh Auth0 `state` server-side and 302s to
    `auth.woolworths.co.nz/u/login/identifier` — confirmed live by
    clicking the real button and reading where it lands, then verifying
    the same URL (with `redirectUrl` pointed at the homepage) reaches
    the identical login form on its own. That `state` is server-minted
    per request, so it can't be hardcoded as a static Auth0 URL — this
    re-requests the redirect every time rather than pointing straight at
    `auth.woolworths.co.nz`.
  - Fulfilment store/delivery-address selection isn't handled — cart-add
    uses whatever context the logged-in session already has active.
  - **Full end-to-end flow confirmed working by Oscar**: real login →
    combined-list cart-add → real Woolworths cart → checkout completed.
    This was never something I could test myself (real credentials), so
    it stayed an open question through most of this feature's build —
    now closed. `"Kg"` pricingUnit specifically (see above, still an
    extrapolation from v1's `"Each"`-only pattern) wasn't necessarily
    exercised by that order — still worth a first-weight-based-item
    check, not re-flagged as fully proven by this.
  - **Confirmed real-cart behavior** (live test, not assumed): cart-add
    *sets* a SKU's quantity rather than adding to it — two separate calls
    for the same SKU (one shopping-list line wanting "21 onions" by
    count, another wanting "500g" by weight, same underlying loose-onions
    SKU) left only the second call's amount in the real cart, silently
    dropping the first. Fixed in `commands.rs`: lines are grouped by SKU
    code and their raw (unrounded) needed amounts summed into one
    `RawCartNeed` *before* rounding — confirmed against the real cart
    (3.7kg combined onions, correct). Rounding-then-summing was
    considered and rejected, since it can badly overcount (five lines
    each needing 100g against a 500g pack would round to 5 packs
    individually, vs. the correct 1 pack for the real 500g combined).
    `RawCartNeed` has two variants, not three: a literal count against an
    `Each` SKU and a weight/volume need converted into pack-equivalents
    against that same SKU are actually the same unit (whole packs) just
    arrived at differently — an earlier version kept them as separate
    variants, which silently dropped one instead of summing when a
    single `Each` SKU had both a count-based and a weight-based line.
  - **Multi-list cart add — implemented.** `add_shopping_lists_to_cart`
    takes `Vec<i64>` of list ids and merges by SKU across *all* of them
    at once, for the same reason two lines within one list merge: the
    cart-add sets rather than adds per SKU, so two lists both wanting
    onions must become one combined quantity. A single list (the detail
    page's own "Add to cart") is just this called with a one-element
    vec — `CartAdd.svelte` always calls this one command, never a
    separate single-list variant, so there's exactly one copy of the
    merge logic. (A thin `add_shopping_list_to_cart` wrapper existed
    briefly for the old flat `/shopping-list` page; removed along with
    that page — see "Old pages" below.) Unit-tested in `commands.rs`'s
    `mod tests` — cross-list summing and the merge-before-round rule.
  - **Login state is checked with a real request, not cookie names.**
    `woolworths_cart::check_logged_in` does `GET /api/v1/trolleys/my`
    (confirmed: 401 with zero cookies, 200 with a session) rather than
    trusting cookie-name sniffing. **Bug found and fixed**: it used to
    keep a `CookieJar::is_authenticated()` pre-check that looked for
    v1's Keycloak-era cookie names (`KEYCLOAK_IDENTITY`,
    `ASP.NET_SessionId`, ...) and short-circuited to `false` before ever
    making the real request if none were present. Since **Woolworths'
    login is now Auth0** (`auth.woolworths.co.nz/u/login/identifier?state=…`)
    and doesn't set any of those, this silently reported "not logged
    in" for every real session — both `check_logged_in` itself (so
    Settings' status pill *and* the CartAdd pre-flight check both lied)
    and, separately, `add_all`'s own copy of the same gate (so even
    after the frontend's pre-flight check somehow passed, the actual
    cart-add command rejected it anyway with "Not logged in to
    Woolworths yet"). Fixed by deleting `is_authenticated` entirely and
    having both call sites always hit the real trolley endpoint — no
    known-reliable Auth0 cookie names exist to sniff for instead.
  - **Cart page URL is `/reviewtrolley`** — confirmed by reading the
    cart link off woolworths.co.nz itself. `/trolley` renders their
    404 page; the SPA returns HTTP 200 with an empty `<title>` for
    *every* path, so status codes and server-side fetches are useless
    for checking whether a route is real — it has to be loaded in a
    browser. `open_woolworths_cart` opens it in its own app window,
    sharing the WebView2 profile (so it's already signed in).
  - **Saved login across restarts — inconclusive, needs a real test.**
    The app has a persistent per-app WebView2 profile at
    `%LOCALAPPDATA%\com.oscar.kai\EBWebView`, so cookies *can* survive a
    restart. But its `Default/Network/Cookies` store contained **zero**
    woolworths.co.nz entries after a session where cart-add demonstrably
    worked — meaning the auth cookies were never written to disk. Two
    explanations, not yet distinguished: (a) they're session cookies
    that live only in memory by design, or (b) they were still in memory
    when the process was force-killed (`taskkill /F` was used repeatedly
    during that session, which skips WebView2's flush on clean exit).
    **Don't assume either.** The way to settle it: sign in, close the
    app *normally*, reopen, and read Settings → Woolworths account. If
    they turn out to be session-only, there's nothing app-side to fix —
    that's Woolworths' server deciding the session's lifetime.

## Settings — implemented

- Gear button top-right of the `/app` header opens `Settings.svelte`, a
  separate full-window area with its own back button. Deliberately a
  container that grows; Woolworths account was the only section at
  first, now joined by delivery fee (below).
- Shows live sign-in state (via the real `woolworths_login_status`
  probe above), a "Log in to Woolworths" button reusing the existing
  login window, and a "Check again" button — which is also how you'd
  empirically answer the session-persistence question above.
- **Delivery fee** — a single number, editable here, same
  implicit-save-on-blur pattern as everywhere else. Backed by a new
  generic `settings` key-value table (`db::settings`) rather than a
  dedicated column, since this is exactly the shape most future
  one-off settings will be (one value, no relations) — avoids a
  migration per setting. Defaults to $14 (Oscar's stated usual fee)
  when unset. Not fetched from Woolworths — nothing in their product
  or cart API exposes a delivery cost, so it's a plain user-entered
  constant, changeable here since real delivery pricing can vary by
  address/timeslot.

- **Settings layout & scrolling.** The sections sit in CSS columns
  (`column-width: 25rem`, so as many columns as fit, one when narrow;
  columns rather than a grid because the sections are very different
  heights and columns pack them without gaps; `break-inside: avoid` keeps
  a section whole). The window itself must never scroll — `html, body`
  are `overflow: hidden` in the app shell — and `.content` gets
  `overflow-y: hidden` (class `locked`) whenever Settings, an item/recipe/
  list view or the Edit tag dialog is open over it, so the list beneath
  can't keep a second scrollbar of its own. Its scroll position is kept.
  Honest note: a window-level double scrollbar could not be reproduced
  in the browser harness at several window sizes; the nested-scroller case
  (a full-screen view open over the scrollable list) could, and both are
  now closed off.

## Backup / export — implemented (export only, no restore)

- **Settings → Backup → "Export data"** downloads the shared server's whole
  database as a zip, saved straight into the Downloads folder as
  `kai-backup-2026-10-06_14-32-05.zip` (the user's *local* time, to the
  second; if that name is taken it becomes `-2`, `-3`, … — an existing
  backup is never overwritten), then shows the path and a "Show in
  folder" button (`revealItemInDir`, capability
  `opener:allow-reveal-item-in-dir`). No Save-As dialog — that would need
  a new Tauri plugin for a click the user didn't ask for.
- **Server only, by decision.** The button is disabled with an
  explanation in Local mode; the app's own SQLite data is *not* covered.
  The Tauri command `export_backup` refuses unless the saved mode is
  remote with a saved URL, and it reads the config straight from the
  local settings table (like `test_remote_connection`, not through the
  `Backend` trait — export is not a data operation both backends share).
- **The server builds the zip**: `GET /export` (token-protected, like
  everything but `/health`), `Cache-Control: no-store`,
  `crates/kai-server/src/routes/export.rs` + `db/export.rs`. Inside:
  `manifest.json` (format 1, `exported_at` UTC, server version, row count
  per table) and one pretty-printed `<table>.json` per table, **all ten**
  (`items, skus, tags, item_tags, recipes, recipe_items, recipe_tags,
  shopping_lists, shopping_list_items, settings`), each a list of rows
  with their original ids so every relationship survives.
  - Postgres makes the JSON itself (`jsonb_agg(to_jsonb(t) ORDER BY …)`),
    so a column added by a future migration is exported with no code
    change. **A new *table* must be added to `db::export::TABLES`** — the
    integration test asserts every table is in the manifest, so
    forgetting fails loudly.
  - All tables are read in **one `REPEATABLE READ` read-only
    transaction**: one consistent snapshot even if someone edits while it
    runs (no list line pointing at an item deleted a moment earlier).
  - **Holds no secrets**: the shared token is in the server's
    environment, not the database; images are links, not files. So a
    backup is safe to keep around, but it is still all of the household's
    data.
  - Built in memory — the whole database is a few MB at most.
- **Format decision**: JSON per table rather than a `pg_dump` SQL file
  (would need `pg_dump` in the server image and is useless without
  Postgres) or CSV (flattens the images/allergens lists). JSON is
  readable, portable, and easy to load back with a script.
- **No restore, deliberately.** Overwriting live data is a separate, much
  riskier feature than reading it. Until it exists a backup is restorable
  by script (ids, links and timestamps are all in the files), not by a
  button.
- **A server from before this existed** has no `/export`; its static-file
  handler answers 404/405, which the app turns into "This server is too
  old to export — update it" instead of a bare status. So the desktop
  needs the server redeployed before the button works.
- Verified: `thin_client.rs` against real Postgres (401 without a token,
  zip headers, every table present, real rows and ids, the Onion↔Veg
  link, timestamps as strings, empty tables as `[]`);
  `remote_backend.rs` runs the desktop's actual `download_backup` against
  a real server (contents, and a wrong token's error); unit tests for the
  zip layout, the filename, and never-overwrite. **Not looked at in the
  real window**: the Settings section itself (its updater/version calls
  need the real Tauri runtime, so it couldn't be driven in a browser) and
  the actual save into the Downloads folder.

## Windows dev environment notes

- `tauri dev` opening a blank window for ~25-30s before content appears (on
  every relaunch, not just first-ever) was **not** compile time and **not**
  Windows Defender — confirmed via Chromium netlog capture
  (`WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS=--log-net-log=...`). Root cause:
  Windows' "Automatically detect settings" (WPAD proxy auto-discovery) was
  on, and every fresh WebView2 process tried resolving `http://wpad/wpad.dat`
  before timing out (~26s) and falling back to direct. Fixed by disabling
  that toggle in Settings → Network & Internet → Proxy — a per-machine OS
  setting, not something in this repo.
- Vite's `server.host: false` default resolved to IPv6-loopback-only on this
  machine (`[::1]`, no `127.0.0.1` listener) — harmless once the WPAD issue
  above was found, but still pinned `vite.config.js`'s `host` and
  `tauri.conf.json`'s `devUrl` to `127.0.0.1` explicitly to remove the
  ambiguity.

## Woolworths NZ API (confirmed live, no auth required)

- Search: `GET https://www.woolworths.co.nz/api/v1/products?target=search&search={query}&inStockProductsOnly=false&size={n}`
- Product detail: `GET https://www.woolworths.co.nz/api/v1/products/{sku}`
  → richer than search results: adds `genericName`, `breadcrumb`
  (department/aisle/shelf), multiple `images`, `healthStarRating`, `origins`,
  `description`, `allergens`, `claims`, `ingredients`, `nutrition` table, plus
  the same `price`/`size`/`quantity` blocks. **This is the endpoint
  `fetch_woolworths_sku` actually uses** — the search endpoint returns a
  thinner shape and was only used for exploration.
- Key fields beyond the obvious price/size ones, confirmed by direct API
  inspection (not assumed):
  - `unit` (top-level, string): `"Each"` for discrete items, `"Kg"` for
    loose/weighed ones. Reliable across produce, meat, seafood, deli,
    packaged goods — no ambiguous cases found.
  - `quantity.min` / `.max` / `.increment`: the actual purchasable
    granularity for that unit (e.g. loose onions: min 0.1kg, 0.1kg steps;
    salmon fillets: min 0.32kg, 0.1kg steps). This is what lets a recipe's
    needed amount get rounded to something actually orderable later, not
    just a yes/no "sold by weight" flag.
  - `supportsBothEachAndKgPricing` (bool) + `averageWeightPerUnit`: some
    SKUs (confirmed: loose onions, sku 144329) let the shopper choose
    Weight *or* Quantity mode at add-to-cart time on Woolworths' own site
    (a literal radio toggle) — `unit` above is only the default in that
    case. `averageWeightPerUnit` (kg, only populated when true) is the
    conversion factor between the two modes.
  - `price.promotionStartDate` / `.promotionEndDate`: ISO-ish strings
    (`"2026-08-24T00:00:00"`), only populated when `price.isSpecial` is
    true. Confirmed via a live special (sku 269671).
  - `breadcrumb.department/aisle/shelf`: not yet parsed into our `Sku`
    model — see "not yet implemented" below.
- Cart-add (`POST /api/v1/trolleys/my/items`) requires an authenticated
  session — confirmed via a zero-cookie request hard-401ing, no anonymous
  cart exists. Not needed for read-only product data. See "Woolworths
  cart interaction — implemented" above for how auth is actually sourced.

## Prior art worth referencing (on `main`, not carried forward as code)

- `kai/objects/item.py` — old Item model: name, stock_code, cached
  `online_data`, tags, is_long_term, sold_by_weight, default_weight_kg.
- `kai/objects/woolworths_data.py` — old product-fetch + field extraction.
- `kai/objects/price_history.py` — separate price-snapshot store keyed by
  item id, with min/max/avg-in-window helpers.
- `kai/server/` — old FastAPI-ish backend for remote/client-server mode.

## Item/SKU domain model — current state

- **Item = a concept** the user tracks (e.g. "Milk"), not a single product.
  Holds one or more **linked SKUs** for price comparison. An item can have
  just one SKU if that's all that's relevant.
- **Item table** (`items`): `name`, `is_perishable` (bool, default true —
  drives shopping-list auto-generation later: perishables like veg/milk get
  re-added most trips, non-perishables like salt/spices shouldn't be; a
  dedicated typed column rather than a tag, since it's read by logic, not
  just displayed).
- **Tags**: normalized (`tags` + `item_tags` join table, case-insensitive
  unique names), not a JSON column — chosen so tags can be listed/reused/
  autocompleted and (later) filtered on directly. Freeform, purely
  descriptive (unlike `is_perishable`).
- **Each linked SKU** (`skus` table) caches, from the provider's product API:
  - Identity: `provider` (e.g. `"woolworths"`) + `sku`, unique per item
  - `name`, `brand`, `variety`
  - `price`: current, original, is-on-special flag, save %,
    `promotion_start_date`/`end_date`
  - `size`: `cup_price` + `cup_measure` (price per unit, e.g. $/1L) — the
    real cross-SKU comparison metric, not raw price, since SKUs can be
    different pack sizes. Plus `package_type`/`volume_size` (human-readable).
  - `quantity`: `unit` ("Each"/"Kg"), `min`/`max`/`increment` (purchasable
    granularity), `supports_both_units`, `average_weight_per_unit` — see API
    notes above. This is what "only order the amount a recipe needs" will
    key off later.
  - `availability_status` / `stock_level`, `images`
  - `allergens`, `ingredients` — important: Oscar's partner is gluten free,
    so allergen flagging is a real requirement, not a nice-to-have. Woolworths
    returns allergens as a structured list (e.g. `"Contains Milk"`); used
    directly for badges. Ingredients (free text) is backup for cases the
    allergens list doesn't catch.
- **Not yet implemented**: `breadcrumb` (department/aisle/shelf) — would let
  a shopping list sort itself by aisle later. Lower priority, deliberately
  deferred, not forgotten.
- **Explicitly excluded, not planned for now**: `barcode`, `healthStarRating`,
  `description`, `claims`, full `nutrition` table. Easy to add later from the
  same API response if needed — not a re-architecture.
- **Price history — decided, not yet implemented.** Per-SKU only: time-series
  snapshots keyed by SKU, same idea as the old `PriceHistory` object. No
  item-level average and no item-level rollup/trend — deliberately rejected.
  "Did this item get more expensive" is answered by looking at individual
  SKUs' own history, not a derived combined metric. This is the next
  significant feature area, separate from the field-level gaps above.
- Implicit-save UX: item name auto-saves/creates on blur (not per-keystroke);
  a SKU auto-saves the moment its fetch succeeds; tags/perishable-toggle
  auto-save on the action. No explicit "Save" button anywhere — only
  "Delete" is a deliberate, explicit action. Recipes follow the identical
  pattern (see below).

## Recipe domain model — current state

- **Recipe table** (`recipes`): `name`, `method` (single freeform text
  column). Same implicit-save UX as everything else: both auto-save on
  blur, no separate save button. Method started as a per-step table
  (`recipe_steps`, one row per step) but Oscar wanted it simpler — just
  one text box, written however feels natural, not structured into
  discrete rows. That table was dropped in the very next migration before
  it shipped anywhere; not a design still in flux, a closed decision.
  Also carries `servings` (nullable int — what the `recipe_items` amounts
  below are actually for, needed to scale a recipe before it hits a
  shopping list later) and `source_url` (nullable text, just a reference
  link, no validation).
- **Recipe tags**: reuses the same `tags` table Items already use (shared
  vocabulary — "quick"/"vegetarian" makes sense on either), via a
  separate `recipe_tags` join table. Same auto-save-on-add UX as item
  tags.
  - **New-UI sidebar display — reconsidered, decided.** The shared pool
    above is still one table, but the `/app` Pantry/Recipe Book sidebar
    doesn't list *every* tag that's ever existed — it only lists tags
    actually in use by whichever tab is active (derived client-side from
    the tags already loaded per item/recipe card, no separate query). An
    item-only tag doesn't clutter the Recipe Book sidebar until a recipe
    actually uses it too, and vice versa. Considered fully separate tag
    pools per domain instead (no shared vocabulary at all) and explicitly
    rejected — this keeps the shared table's reuse benefit while fixing
    the actual complaint, which was display noise, not the data model.
  - **Sidebar toggle emoji — implemented, pills stay plain text.** Each
    tag's sidebar button (one combined pill: emoji + name) shows an
    emoji — auto-picked client-side (`autoEmojiForTag` in `+page.svelte`,
    a keyword-substring lookup against the tag name, `🏷️` fallback) or,
    if the user's overridden it, `tags.emoji` (nullable `TEXT` column,
    `null` = "use auto"). Deliberately **not** shown on the plain tag
    pills on item/recipe cards — cosmetic sidebar flourish only, kept out
    of the denser card view. Override via a hover-revealed "✎" inside the
    pill (`e.stopPropagation()`'d so it doesn't also toggle the filter),
    which now opens the **Edit tag dialog** (below) — emoji input with the
    same blur-to-save pattern, plus a "Reset emoji to auto" that clears
    the override back to `null` rather than guessing a specific
    replacement emoji. `set_tag_emoji` updates every copy of that tag
    across `cards`/`recipeCards` (each card fetched its own separate copy
    via `list_tags_for_item`/`list_tags_for_recipe`, so a single object
    mutation wouldn't reach the others) rather than reloading everything
    from scratch.
  - **Edit tag dialog / bulk tag edit — implemented** (`TagEditor.svelte`,
    desktop only; the phone app has no tag editing). The ✎ used to open a
    tiny inline emoji strip; it now opens a modal that works on the tag
    **everywhere at once** — Pantry and Recipe Book share the one `tags`
    row, so there's no per-tab version of it:
    - **Rename** (`rename_tag`): saves on blur/Enter like everything else,
      and shows on every item and recipe immediately since it's one row.
      A name another tag already has (case-insensitively) is **refused**
      with "A tag called 'X' already exists" rather than merged — merging
      is destructive and was deliberately left for a feature of its own.
      Changing only the case of the tag's own name is allowed.
    - **Used by**: checklists of every item and recipe, ticked where the
      tag already applies, with a search box and "Select shown / Clear
      shown" (which act on what the search currently shows). Ticks are
      only **staged** — nothing is saved until **Apply N changes**, so a
      big batch can be reviewed or abandoned. This is the one place the
      app's implicit-save rule is broken on purpose (chosen by Oscar):
      accidentally unticking 30 items shouldn't have already happened.
    - `apply_tag_changes` takes a **diff** (`TagMembershipChanges`:
      add/remove item ids and recipe ids), not the final membership, so a
      change made by the other person since the dialog opened isn't
      overwritten for items you didn't touch. It runs in one transaction —
      an unknown id anywhere rolls the whole batch back (unit-tested on
      SQLite, and through `RemoteBackend` against real Postgres in
      `remote_backend.rs`). Removals apply before additions; re-tagging
      something already tagged is a quiet no-op.
    - The dialog keeps its own copy of the tag (`editingTag`) because a tag
      drops out of the sidebar the moment nothing on the current tab uses
      it, which would otherwise pull the dialog out from under an
      in-progress edit. After Apply the on-screen cards are patched in
      place rather than reloaded.
    - Verified by running the real `/app` page in a browser against an
      in-memory fake of Tauri's `invoke` (a throwaway Vite config, deleted
      afterwards): dialog pre-ticks the right rows, a clashing rename
      shows the error and reverts the field, a real rename and emoji
      change/reset reach the sidebar, and Apply sends exactly the
      difference. **Not tried in the real Tauri window.**
- **Recipe ↔ Item links** (`recipe_items` join table): a recipe can hold
  multiple items. Adding an item to a recipe reuses an existing item by
  name (case-insensitive match against everything in the Pantry) if one
  exists, otherwise creates a new one — mirrors how the Pantry itself
  never makes you pick from a rigid list.
- **Quantities — decided, implemented.** `recipe_items.amount` (nullable
  REAL) + `recipe_items.unit` (nullable TEXT, validated in Rust against
  `recipe_items::VALID_UNITS`, not a DB constraint). The unit set is
  deliberately narrow: **`g`/`mL`/`count` are real, shopping-relevant
  amounts** (`count` for "3 onions"-style discrete amounts, matched
  against an "Each"-purchased SKU) — **`tsp`/`tbsp` are nominal**
  (cooking reference on the recipe, never fed into shopping-list math).
  No `cup`, no arbitrary units.
  - This was a conscious simplification of what was originally scoped as
    a general "unit-conversion layer" (converting arbitrary recipe units
    like cups to purchase units). That general version needed
    ingredient-specific **density** to cross between mass and volume
    (1 cup flour ≠ 1 cup rice by weight) — the genuinely hard, long-tail
    part of the problem. Restricting recipe input to g/mL for anything
    that should actually drive shopping removes the need for density
    entirely: g stays in the mass world, mL stays in the volume world,
    and matching against a SKU's own pack size/`quantity` block (see
    above) is pure within-dimension arithmetic. tsp/tbsp become pure
    display labels with zero math attached.
  - Still open, not urgent: matching a `g`/`mL` amount against a linked
    SKU still needs a small parser for Woolworths' own size strings
    (`"500g"`, `"1.5kg"`, `"2L"`, `"6pack"` — confirmed by a live sweep of
    ~470 products, a narrow single-source format, not general recipe-text
    parsing) plus a packing/rounding solver using `quantity.min/increment`
    (already stored). Genuinely unconvertible case: a recipe wanting a
    *count* (not weighed) against a SKU that's weight-only with no
    `average_weight_per_unit` — flag it, don't guess, same rule as
    everywhere else in this app.

## Shopping list domain model — current state

- **Multiple named lists** (`shopping_lists`), same pattern as
  Items/Recipes — not one ongoing list. Same implicit-save UX (name
  auto-creates/syncs on blur).
- **Lines** (`shopping_list_items`): each is an item + `amount`/`unit`
  (only `g`/`mL`/`count` — the same real-units set `recipe_items` uses,
  tsp/tbsp never reach here) + a chosen `sku_id`. No uniqueness
  constraint in the schema on (list, item) — **merging is handled in
  Rust**, not enforced by the DB: adding an item that's already on the
  list with the *same* unit sums into that line; a different unit for an
  item already present becomes its own separate line rather than
  something to reject or coerce.
- **Adding a recipe** expands its `recipe_items` ingredients onto the
  list, scaled by `target_servings / recipe.servings` — falls back to
  1:1 if either side's servings isn't set. Recipes must already exist
  (no inline create, unlike items — too much setup to spin up on the fly
  from a text box). Three kinds of ingredient are skipped rather than
  added: `tsp`/`tbsp` (nominal, never real amounts), ones with no amount
  set, and — new — **non-perishable ingredients** (salt, spices, tinned
  goods, ...), since those usually outlast a single shopping trip and
  auto-adding one every time a recipe using it goes on a list would mean
  re-buying things you almost certainly already have. See the omission
  check below for the safety net on that last one, for when something's
  genuinely run out.
- **Pre-checkout omission check — implemented.** `CartAdd.svelte`'s
  send flow (see below) runs `list_omitted_shopping_list_items` after
  confirming login and before actually sending — a review pop-up shown
  only if it finds something, never adding friction to the common case.
  Two categories (`shopping_list_items::list_omitted`):
  - **Recipe ingredients not on this list**: for every recipe that
    genuinely has a line on the list(s) being checked out (via
    `source_recipe_id`), any of its *other* ingredients with no
    corresponding line — whatever the reason (nominal unit,
    non-perishable, unset amount, or just removed by hand). Recomputed
    fresh at checkout rather than remembering *why* something was
    skipped at add-time — simpler, and catches manual removals too.
  - **Perishables you might've forgotten**: perishable items linked to
    *any* recipe anywhere (not just ones on this list) that aren't
    already flagged above and aren't already on the list — the broader
    "you cook with this regularly, did you just run out?" reminder.
    Deliberately scoped to recipe-linked items, not every perishable
    ever catalogued — an explicit choice to avoid flagging pantry items
    that aren't part of any routine.
  - **Each row's "+ Add" is purely local state — never written to
    `shopping_list_items`.** First version called
    `add_item_to_shopping_list`, same as a plain item-drop — wrong,
    confirmed live: writing it to the list meant it just sat there
    forever (nothing ever clears a list's lines), so the very next
    checkout saw it as "already on the list" and silently stopped
    flagging it — the opposite of what a "did you run out?" reminder
    should do, and the list itself picked up a permanent stray line
    (`rice`, `100g`) the user never actually meant to keep there. Fixed:
    "+ Add" moves the pick into `CartAdd.svelte`'s own `extraItems`
    array (component state, reset at the start of every `send()`), and
    `add_shopping_lists_to_cart`/`add_shopping_list_to_cart` both take an
    `extra_items: Vec<ExtraCartItem>` param — resolved to a SKU need
    (same `cheapest_sku_id` a fresh item-drop would use) and merged into
    the same send as the real list lines, but never persisted anywhere.
    The list stays exactly what's really on it; a one-off "I do need
    this today" only affects the cart going out right now, and gets
    asked about again next time.
  - "Continue to cart" proceeds regardless of what's left unadded —
    this is a reminder, not a gate.
  - **Pop-up shows a running total, including delivery.** Computed via
    the same `priceSkuGroups`/`sumSkuGroupTotals` (shoppingListPricing.ts)
    the Shopping Lists tab and detail page use — the real list's lines
    plus a synthetic line per staged `extraItem` (priced by its cheapest
    linked SKU, a plain estimate — not necessarily the exact SKU the
    real send resolves to). Recomputed from scratch on every "+ Add",
    not incremented, so it can't drift from what the actual send will
    total.
- **Adding an item** reuses an existing item by name (case-insensitive)
  or creates one — same pattern as Items/Recipe-item-linking.
- **Cheapest-SKU auto-pick**: on a new line, compares linked SKUs by
  plain `sale_price` — total cost, what you'd actually pay. `None` if
  the item has no linked SKUs at all — flagged in the UI ("no SKU
  chosen"), not guessed. Swappable per line via a dropdown of that
  item's other linked SKUs (reuses the existing `list_skus_for_item`
  command; the new `/app` UI's version of this dropdown is a minimal
  image+name+price picker under a small ▾ next to the SKU name).
  - **Reversed from `cup_price`.** The original version compared by
    `cup_price` ($/kg or $/L — the correct metric for "which pack is
    the better per-unit deal," comparable across different pack sizes).
    Changed because that's not actually what "auto-pick the cheapest
    one for my list" should mean: a smaller pack that costs less
    overall was losing the auto-pick to a bigger pack with a better
    per-kg rate but a higher total price. `cup_price` is still stored
    and shown (e.g. "($2.49/1kg)" next to a SKU) since it's still useful
    for a shopper comparing options by hand — just no longer the
    auto-pick's sort key.
  - **Preferred SKU — trumps `cheapest_by` entirely.** A star (☆/★) on
    each SKU widget in the item detail page. At most one preferred SKU
    per item — setting one clears any other (`db::skus::set_preferred`),
    enforced in Rust rather than a DB constraint. `cheapest_sku_id`
    checks for a preferred SKU first, unconditionally, before even
    looking at `cheapest_by`. Only affects future auto-picks (new
    shopping-list lines); doesn't retroactively change a SKU already
    resolved onto an existing line — same as toggling `cheapest_by`
    itself doesn't.
- **Buy-quantity calculation — split across two places, neither called
  "buyQuantity()" anymore.** Originally a single frontend helper in the
  old flat `/shopping-list` page (removed once `/app` fully replaced it
  — see "Old pages" below); its two purposes now live separately:
  - **On-screen preview** (`ShoppingListDetail.svelte`'s `skuGroups`):
    parses the chosen SKU's own `size.volume_size` label ("700g",
    "1.5kg" — narrow single-source parser, only the plain
    `<number><unit>` shape, not multi-packs/ranges/"min order …") to
    work out a whole-pack count for `Each`-sold SKUs; for dual-mode SKUs
    (`supports_both_each_and_kg`, e.g. onions) shows **both** a weight
    and an each figure side by side rather than picking one — the
    quantity block Woolworths gives us only describes the SKU's
    *default* mode's granularity, so onion-count isn't roundable against
    the *weight* mode's 0.1kg `quantity.increment`. This preview is
    **not** rounded to `quantity.increment` for a weight-sold SKU — it
    just shows the raw combined need (see `weightCost`/`weightPill`) —
    so it can show a slightly different number than what actually gets
    ordered.
  - **The real, pack-rounded quantity that actually gets ordered**
    (`commands.rs`'s `RawCartNeed`/`round_to_increment`, used by
    `add_shopping_lists_to_cart`): this is authoritative — it's what the
    real Woolworths cart-add sends, unit-tested (`cargo test --lib`),
    and correctly merges same-SKU needs across lines/lists *before*
    rounding (see "Confirmed real-cart behavior" above).
  - Still unhandled, shows "can't compute — check manually" in the
    preview: a `count` need against a plain `Kg`-only SKU with no
    `average_weight_per_unit` (no dual-mode data to convert with) — the
    same genuinely-unconvertible case flagged elsewhere, not a new gap.
- **Idea, not started**: when an item is added to a shopping list, its
  linked SKUs should get auto-refreshed from Woolworths at that point
  (reusing the `refresh_skus_for_item` command below) — the moment
  you're about to actually shop is exactly when stale price/special/
  stock data matters most. Noted during the SKU-refresh work below, not
  acted on yet.
- **Cart-add UI (new `/app`)** lives in one shared `CartAdd.svelte` —
  used both by the Shopping Lists tab's multi-select toolbar and by a
  single list's own detail page, so the two flows can't drift. It owns
  the whole sequence: check sign-in → prompt to log in if signed out
  (rather than firing a request that just 401s) → check for omissions →
  review pop-up if it finds any (see above) → send → show a summary of
  what landed vs. what didn't → open the cart window. Login is checked
  *before* the omission check, deliberately — no point reviewing
  anything if the next step would just be "go sign in and try again".
  The cart is deliberately **not** opened when nothing succeeded —
  jumping to an unchanged cart after a total failure just reads as a bug.
- Lists are ticked via a checkbox on each card (its click is
  `stopPropagation`'d so ticking doesn't also open the detail view).
  Selections are pruned against the live list set on every reload, so a
  deleted list can't linger as a ticked-but-missing id.
- **Per-list and combined-selection pricing share one function
  (`shoppingListPricing.ts`).** Used to be two independent
  implementations: the Shopping Lists tab's card total summed each
  line's raw `sale_price` with no regard for amount, while
  `ShoppingListDetail`'s "SKUs needed" section correctly scaled a
  weight-based line by `cup_price × grams/1000`. They drifted — a 450g
  onion need showed $2.49 on the card, $1.12 on the detail page. Now
  both call the same `priceSkuGroups`/`sumSkuGroupTotals` over the same
  full SKU data, so they can't disagree again. When multiple lists are
  ticked, the toolbar shows their combined total (a plain sum of each
  selected card's own already-correct total) as a pill under the
  cart-add button, plus a smaller sub-line adding the delivery fee
  (see Settings above) to show what the real checkout total would be.

## SKU refresh — implemented

- SKU data is a one-time snapshot from whenever it was (re-)fetched —
  nothing crawls Woolworths automatically or on a schedule. Two Tauri
  commands cover manual refresh: `refresh_sku` (one SKU, by its stored
  id — looks up its stock code and item id, re-fetches, upserts) and
  `refresh_skus_for_item` (every SKU linked to an item, sequentially —
  one Woolworths request per SKU, not parallel, so one failure doesn't
  lose progress on the others already done). Both just re-run the same
  fetch+upsert path `save_sku_to_item` already uses.
- Three entry points in the new `/app` UI, all calling the same two
  commands: a small circular ⟳ next to "SKUS: n" on each Pantry widget
  (refreshes that item's SKUs), a "⟳ Refresh all" button in the item
  detail page's SKUs section header (same, from inside the detail view),
  and a per-SKU ⟳ next to each SKU's delete button in the detail view
  (`refresh_sku`, just that one). Plus a "⟳ Refresh pantry" button in
  the Pantry toolbar (top right) that walks every item's SKUs
  sequentially, reusing the same per-item refresh path — deliberately
  sequential across items too, not `Promise.all`, to avoid a burst of
  simultaneous requests to Woolworths.

- **Stale-price flag — implemented (14 days).** `skus.updated_at` already
  existed in both databases and is written by the save/refresh upsert and
  *nothing else* (starring a SKU as preferred does not touch it — unit
  tested), so it is exactly "when did we last ask Woolworths". It just
  wasn't on the wire: `StoredSku` now carries `updated_at` (RFC 3339, UTC;
  SQLite's `datetime('now')` is normalised with `strftime`, Postgres's
  `TIMESTAMPTZ` with chrono). `#[serde(default)]`, so a newer desktop app
  still works against a server from before the field existed — it just
  shows no badges until the server is redeployed.
  - **Rule**: an item is flagged if its *oldest* SKU is 14+ days old (the
    cheapest pick compares all of an item's SKUs, so it is only as
    current as the stalest). Unknown dates (older server, a SKU just
    fetched this session) are never flagged — no badge rather than a
    wrong one. The rule lives in `src/routes/app/skuFreshness.ts` and, for
    the phone, `mobile/src/lib/freshness.ts` (a small deliberate
    duplicate — two separate frontends; the phone copy is unit-tested).
  - **Where it shows**: an amber "⚠ Nd old" on each Pantry card next to
    "SKUS: n"; a "Last refreshed 5 days ago · 16 Oct 2026" line under every
    SKU in the item detail (always shown when the date is known — amber
    with a ⚠ once stale; a SKU just added shows "today"); a
    "⚠ price Nd old" in the shopping list's "SKUs needed" rows; and a
    "⚠ Price N days old" line on the phone's Pantry rows. A **"⚠ Refresh
    stale (n)"** button appears beside "Refresh pantry" only while n > 0,
    and refreshes just those items (sequentially, like refresh-all).
    Deliberately just a badge: it never blocks or changes anything.
  - **Designed, not built yet — refresh on add.** Nothing refreshes SKU
    data on add-to-list today (refresh is only ever a button press), and
    nothing crawls on a schedule. Oscar's decisions: when an item or
    recipe is added to a list, refresh its SKUs **if older than 1 day**;
    the add happens **immediately** (the UI must stay responsive) and the
    refresh runs in the background, sequentially; when it lands, a line
    is **swapped to a cheaper SKU** if there is one. Constraints for that
    swap, so it can't undo a choice: only swap a line whose SKU is still
    the auto-pick from when it was added (never one the user changed),
    and use the same `cheapest_sku_id` rule as a fresh add so a starred ★
    SKU still wins. It can be built from existing commands
    (`refresh_skus_for_item`, `cheapest_sku_id`, `set_shopping_list_item_sku`).
    The **phone can't refresh** — the Woolworths fetcher lives in the
    desktop app and the server has none — so adds from the phone stay on
    the old data until a desktop refresh or a server-side fetcher exists.

## Phase B: shared remote database — done

- **Goal**: genuine shared multi-user use (Oscar + partner), not backup —
  local and remote are fully separate datastores, no migration/merge
  tooling. A settings toggle just points the app at one or the other.
  Deployment target: Docker on Oscar's Unraid box, reachable via his own
  domain + Cloudflare Tunnel (already solved, no work needed here); auth
  is a single shared token sent on every request, not per-user login.
  Plan lives at (session-local) `~/.claude/plans/parallel-petting-wilkes.md`.
- **Stage 1 — done. Cargo workspace + `kai-shared` crate.** Root
  `Cargo.toml` is now a virtual workspace manifest (`members = ["src-tauri",
  "crates/kai-shared", "crates/kai-server"]`); the root `Cargo.lock`
  supersedes what used to be `src-tauri/Cargo.lock`. `crates/kai-shared`
  holds pure wire-format structs/consts with zero DB/framework deps
  (`Item`, `Sku`/`StoredSku` + friends, `Tag`, `Recipe`,
  `RecipeIngredient`/`VALID_UNITS`, `ShoppingList`/`ShoppingListLine`/
  `OmissionReport`, `VALID_CHEAPEST_BY`) — moved verbatim out of
  `src-tauri/src/db/*.rs` and `woolworths.rs`, which now just
  `pub use kai_shared::...` them back in, so no other file's imports
  changed. `Deserialize` was added to all of them (previously
  `Serialize`-only) since they're the wire format `RemoteBackend` (Stage 4)
  will (de)serialize over HTTP.
- **Stage 2 — done. `Backend` trait abstraction, still SQLite-only.**
  `src-tauri/src/backend/` has one `#[async_trait] pub trait XBackend` per
  existing `db/*.rs` module (method names matching `commands.rs` function
  names 1:1, e.g. `create_item`, `cheapest_sku_id` — chosen specifically so
  combining all 8 into one blanket `Backend` trait can't collide), plus
  `LocalBackend` (thin `Mutex<Connection>` wrapper delegating to `db::*`
  unchanged). App state is now `Mutex<Arc<dyn Backend>>` instead of a bare
  `Mutex<Connection>`; every `commands.rs` function is `async fn` and goes
  through `backend.method(...).await` rather than calling `db::*` directly.
  Zero behavior change — this stage was required to be invisible to the
  user, confirmed via the existing 3-test `cargo test --lib` suite plus a
  full manual `/app` smoke pass.
- **Stage 3 — done. `kai-server`: standalone Postgres/Axum API.** New
  crate, no `tauri`/`rusqlite` deps at all — Axum 0.8 + `tokio-postgres` +
  `deadpool-postgres` (pool) + `refinery` (migrations, embedded into the
  binary at compile time via `embed_migrations!`, so the runtime image
  doesn't need the `migrations/` folder). SQL itself isn't shared with the
  SQLite side (real dialect differences — identity columns vs
  `AUTOINCREMENT`, native `BOOLEAN`, `TIMESTAMPTZ DEFAULT now()`,
  `RETURNING id` vs `last_insert_rowid()`, `citext` extension in place of
  `COLLATE NOCASE`, `JSONB` vs JSON-as-TEXT) — `kai-server/src/db/*.rs`
  reimplements each `db::*` function's logic against Postgres by hand,
  reusing only `kai-shared`'s types/validation consts as the shared source
  of truth. Auth is Axum middleware checking `Authorization: Bearer
  <token>` against `KAI_SHARED_TOKEN` on every route except `GET /health`
  (unauthenticated, for Docker's healthcheck); `GET /status` is the
  authenticated one-call reachability+auth check `test_remote_connection`
  (Stage 4) will hit.
  - **Verified live, not just compiled** — no Docker or local Postgres
    install exists in the dev sandbox, so `postgresql_embedded` (a
    dev-dependency that downloads and runs a genuine ephemeral Postgres
    binary) backs two real integration tests: `tests/lifecycle.rs` (full
    create-item → link-recipe → expand-onto-shopping-list →
    non-perishable-skip → omission-report → cascade-delete flow, calling
    `db::*` directly) and `tests/http.rs` (real `axum::serve` on a real
    socket, real `reqwest` calls, proving routing/auth/JSON shape). Both
    pass (`cargo test -p kai-server --test lifecycle` /
    `--test http`).
  - **Real bug this caught**: `list_omitted`'s `SELECT DISTINCT
    items.id, items.name ... ORDER BY LOWER(items.name)` — legal in
    SQLite, rejected by real Postgres (`ORDER BY` expression not in the
    `DISTINCT` select list). Fixed by wrapping the `DISTINCT` query in a
    subquery so the outer `ORDER BY` isn't constrained by it. Only found
    because this got tested against a real Postgres rather than reviewed
    statically.
  - **Docker**: `crates/kai-server/Dockerfile` (multi-stage — `rust:1-slim-
    bookworm` builder, `debian:bookworm-slim` runtime), `docker-
    compose.yml` (kai-server + `postgres:16-alpine`, named volume —
    comment notes the Unraid appdata bind-mount swap), `.env.example`
    (`POSTGRES_PASSWORD`, `KAI_SHARED_TOKEN`). Build context is the repo
    root, not the crate directory, since resolving the Cargo workspace
    needs the whole manifest tree visible — the builder stage stubs
    `src-tauri/src/{main,lib}.rs` with empty placeholders so that member
    resolves without ever compiling its real Tauri/WebView deps (which
    need Linux GUI packages the image doesn't have, and which `kai-server`
    never depends on anyway). `smoke-test.sh` is a plain-curl manual
    lifecycle check against a real running instance, for once this is
    actually deployed — the automated tests above already cover the same
    ground against embedded Postgres.
  - **Not built yet, not tried**: an actual `docker build`/`docker compose
    up` run — no Docker in this dev sandbox. First real verification of
    the Docker path happens on Oscar's own machine or the Unraid box
    (Stage 6).
- **Stage 4 — done. `RemoteBackend` + the local/remote mode switch.**
  `src-tauri/src/backend/remote.rs`: one `reqwest` HTTP call per trait
  method, hand-mapped onto `kai-server`'s actual routes (verb, path, and
  request/response JSON shape all matched by hand against the Stage 3
  route files, not regenerated from anything) — e.g.
  `set_item_perishable` is `PATCH /items/{id}/perishable
  {"is_perishable": bool}`, `add_recipe_to_shopping_list` is `POST
  /shopping-lists/{list_id}/recipes {"recipe_id", "target_servings"}`.
  Errors surface the server's real `{"error": "..."}` body when there is
  one (`AppError`'s shape) and fall back to `"Remote server returned
  <status>"` when there isn't (the auth middleware returns a bare
  `401` with no body — confirmed exercised by the test below, not just
  assumed).
  - **`LocalConn` — a connection kept alive regardless of mode.**
    `backend::LocalConn` (`Arc<Mutex<Connection>>`) is `app.manage`d
    separately from `ActiveBackend` and never dropped, so the *setting*
    of which backend to use can always be read/written (`backend_mode`,
    `remote_url`, `remote_token` — three new keys in the existing generic
    `settings` table, see `db::settings::{get_backend_config,
    set_backend_mode, set_remote_config}`) even while `ActiveBackend`
    currently points at `RemoteBackend`, and so the local SQLite dataset
    itself is never closed just because the app is in remote mode —
    switching back to local reopens nothing, it just resumes routing
    through the same connection. `LocalBackend` was changed to wrap this
    same shared `Arc` (previously it owned its own `Mutex<Connection>`)
    specifically so there's exactly one open connection to `kai.db` at
    any time, not two.
  - **`backend::resolve(&LocalConn) -> Arc<dyn Backend>`** is the single
    place either backend ever gets constructed — called once at startup
    (`lib.rs`'s `setup()`) and again by `set_backend_mode`/
    `set_remote_config` (`commands.rs`) every time either setting
    changes, so `ActiveBackend` is always rebuilt fresh from the saved
    config rather than patched in place; the two commands persist their
    setting through `LocalConn` directly (bypassing `ActiveBackend`
    entirely, per the point above) and then swap the managed `Arc` in the
    same call — no restart needed. `test_remote_connection` (a plain
    `reqwest` call, not through `Backend`) is what Settings' future "Test
    connection" button (Stage 5) hits — it takes the *currently-typed*
    URL/token rather than the saved ones, so a user can check before
    committing.
  - **Verified against a real server, not just compiled.** A dev-only
    `kai-server` path dependency (`src-tauri`'s tests only — never a real
    dependency of the shipped app) plus the same `postgresql_embedded`
    trick from Stage 3 backs `src-tauri/tests/remote_backend.rs`: spins
    up a real embedded Postgres + a real `kai-server` via `axum::serve`,
    then drives an actual `RemoteBackend` instance through one path per
    domain (items, a full `Sku` fixture, tags, a recipe with a
    quantities'd ingredient, a shopping list expanded from that recipe,
    delivery-fee round trip, the delete-guard's error text, and a
    real-401-with-no-body auth failure). Passes
    (`cargo test -p kai --test remote_backend`) — this is what actually
    proves the hand-written route/verb/JSON mapping in `remote.rs`
    matches Stage 3's server in fact, not just in the plan each side was
    written from.
- **Stage 5 — done. `Settings.svelte` "Remote server" section.** A
  `[Local] [Remote]` segmented toggle (`.mode-toggle`, a new small widget —
  the existing `.primary`/`.secondary` buttons didn't read as "currently
  selected" the way this needs to); clicking the inactive one opens the
  existing `ConfirmDialog` before it takes effect, since an unexplained
  empty pantry right after switching could otherwise read as data loss to
  a non-technical user (Oscar's partner). URL/token inputs (token as
  `type="password"`) use the same implicit-save-on-blur pattern as
  Delivery Fee, disabled while mode is local. A "Test connection" button +
  status pill (matching the Woolworths section's) calls
  `test_remote_connection` against whatever's *currently typed*, not
  necessarily what's saved.
  - **A real gap this surfaced, fixed before it shipped**: `set_backend_mode`
    originally propagated `backend::resolve`'s error outright, which meant
    picking "Remote" for the very first time (before any URL had ever been
    saved) returned a hard error from the command — but the mode had
    *already been persisted* by that point (`set_backend_mode`'s DB write
    happens before `resolve` is even called), so the toggle would silently
    desync: the saved setting says "remote" but the failed command means
    the frontend never learns that and keeps showing "Local" selected.
    Worse, the URL field is only enabled once mode is remote, so requiring
    a URL to *already* exist before allowing the switch would have made it
    impossible to ever enter one in the first place. Fixed with
    `try_rebuild_active_backend` (`commands.rs`): the mode-switch commands
    now always persist and always return the real saved config; the
    `ActiveBackend` swap only happens if `resolve` succeeds, and silently
    no-ops otherwise (the previously-active backend just keeps serving
    until a subsequent `set_remote_config` call — with an actual URL —
    succeeds). Caught by re-reading the two commands' error paths after
    writing the UI around them, not by a test.
- **Stage 6 — done. Deployed to the Unraid box.** `docker compose up -d
  --build` from `crates/kai-server` (repo at `/mnt/user/appdata/kai/repo`,
  branch `v2`), reachable through the Cloudflare Tunnel at
  `https://kai.oserver.pro`, with the desktop app connected via Settings →
  Remote server. Redeploying is `git pull && docker compose up -d --build`
  (a warm-cache rebuild took about a minute). What the real deploy
  surfaced, none of which a test could have:
  - The first-ever `initdb` took ~57s on that disk (its own fsync alone
    ~28s), past the compose healthcheck's 50s retry budget, so `kai-server`
    gave up waiting on a Postgres seconds from healthy. Fixed with
    `start_period: 60s` on the Postgres healthcheck.
  - `smoke-test.sh` had lost its executable bit (committed from Windows)
    and had an apostrophe inside a `${TOKEN:?…}` message — bash treats a
    quote inside a `${var:?word}` as a quote opener even within double
    quotes, and the error pointed at line 27, nowhere near line 12.
  - **Cloudflare Access (Zero Trust) was intercepting the hostname** with
    an interactive SSO login before requests reached the origin. A
    bearer-token API client can't complete that; from outside it showed as
    a 302 to `*.cloudflareaccess.com`. Fixed by taking the hostname out of
    the Access policy (kai-server's own shared-token auth already gates
    every route).
  - Verified from a different network than the LAN: `/health` 200 without
    a token, `/items` 401 without one and 200 with, a real create + delete
    round trip.
  - Old v1 data (JSON files from the v1 server's `/data` bind mount) was
    migrated in once with throwaway scripts that aren't kept in the repo;
    a tarball of the original JSON is on the Unraid box under
    `/mnt/user/appdata/kai/backups/`. Items and recipes re-fetched SKU data
    live from Woolworths rather than copying v1's stale prices. v1's
    per-ingredient `nominal` flag has no equivalent here, so nominal g/mL
    amounts were roughly converted to tsp/tbsp (1 tsp ≈ 5, 1 tbsp ≈ 15) and
    nominal `ea` (count) ones — which can't be converted — were left as
    `count` for hand-fixing.

## Mobile web app (`mobile/`) — steps 1–2 done

- **Goal**: a limited phone version (Android first): view the pantry, view
  the recipe book with a nicely formatted recipe card, and add items to
  shopping lists — all against the same `kai-server` the desktop uses.
  Remote-only: no local mode, and no Woolworths cart (that needs the
  desktop app's own login webview).
- **Decided: an installable web app (PWA), not Tauri Android.**
  - Oscar's partner isn't technical: with a PWA she opens a URL once,
    taps Install, and updates arrive the next time she opens it. Tauri
    Android would mean sideloading an APK per update
    (`tauri-plugin-updater` is desktop-only), a signing keystore with the
    same no-recovery property as the updater key, an Android SDK/NDK
    toolchain that isn't set up on this machine (checked: no
    `ANDROID_HOME`, `adb`, NDK or Rust Android targets), and a CI job.
  - UI reuse would have been small either way: the desktop UI is
    desktop-only (zero `@media` queries, fixed-width sidebars) and every
    call is a Tauri `invoke`, so a phone UI is new work regardless.
  - Escape hatch: if Android-only capabilities are ever needed, wrap the
    same UI in Tauri then.
- **Hosted by `kai-server` itself**, at the site root of the same address
  as the API (`https://kai.oserver.pro/`). Same address = same origin, so
  there's no CORS to configure and the app's calls are plain relative
  paths (`/pantry`). Considered and not chosen: hosting the static files
  elsewhere (e.g. Cloudflare Pages) — would need a CORS layer and a
  configured API address, in exchange for shipping UI changes without
  rebuilding the server image.
  - `routes::with_static_files(router, dir)` serves a folder through
    tower-http's `ServeDir`, **outside** the token check — the bundle
    holds no secrets and has to load before anyone can type a token into
    it — while every API route stays behind `require_token`. Enabled by
    the `KAI_STATIC_DIR` env var (the Docker image sets it); unset = API
    only, exactly as before.
  - **No SPA catch-all, on purpose**: an unknown path 404s rather than
    returning `index.html` with a 200, which would turn a mistyped API
    route into an HTML page a JSON client chokes on.
  - `Cache-Control: no-cache` on the static files (revalidate every
    time, a cheap 304 when unchanged) so a redeploy reaches phones on
    their next open instead of when a heuristic cache expires.
- **Two bulk read endpoints**, added because the per-resource routes would
  make a phone do ~`2 × items` requests to draw the pantry (180 for 90
  items) over mobile data and a tunnel: `GET /pantry` (every item with its
  SKUs and tags — the desktop's `ItemCard` shape) and `GET /recipe-book`
  (every recipe with tags *and ingredients*, so a recipe card opens with no
  second request). Composed from the existing `db::*` functions, no new
  SQL; the same N+1 still happens, but against a database on the same box.
  Also what makes an offline cache cheap later: each screen is one JSON
  document. (`routes/overview.rs`.)
- **Stack**: Vite + Svelte 5 + TypeScript, no SvelteKit, no router library
  (the URL hash is the route, so the phone's own Back button closes a
  recipe card). Same dark palette as the desktop. The shared token is
  checked against `/status` before it's saved and stored in
  `localStorage`; a token the server later rejects drops back to the token
  screen with an explanation rather than showing an empty app.
- **Step 1 — done: read-only Pantry and Recipe Book.** Pantry: search, tag
  filter (several tags narrow the list, like the desktop sidebar),
  alphabetical, image + cheapest price with the was-price on a special.
  Recipe Book: compact list, then a recipe card (full-bleed photo,
  servings/ingredient-count/source pills, ingredients with quantities in
  their own aligned column, method as numbered steps).
  - Display rules worth knowing: quantities show fractions (`½`, `1½ tsp`,
    not `0.5`); a `count` ingredient shows just the number; an ingredient
    with no amount shows no quantity. **The method's numbering is inferred
    from line breaks** — it's freeform text, usually written one step per
    line, so lines become numbered steps (any `1.`/`2)` the author typed is
    stripped so it doesn't read "1. 1. Mix…"); a single line stays a
    paragraph. A source link is only clickable if it's really `http(s)`.
    The recipe list is newest-first, same as the desktop (not alphabetical
    like the items list).
  - `Picture.svelte` shows a letter tile while a photo loads, and keeps it
    if the photo fails: on mobile data product photos arrive one by one,
    and without this each was a blank white disc until its turn (seen in
    the first screenshot, then fixed).
- **How it was verified, and what wasn't.**
  - `crates/kai-server/tests/thin_client.rs`: against a real embedded
    Postgres and socket, the app loads with no token, the API is still 401
    without one, an unknown path 404s, `/pantry` and `/recipe-book` return
    the right shapes (including case-insensitive alphabetical order).
  - The UI was exercised in a phone-sized browser against a seeded
    throwaway server — `cargo run -p kai-server --example dev_server`
    (embedded Postgres + seed data + the built app on `127.0.0.1:8799`,
    test token defined in the example; nothing real is touched). The seed
    deliberately includes edge cases: an image that won't load, an item
    with no SKU, a special, a long name, a recipe with no image/servings/
    method, fractional tsp/tbsp, numbered and un-numbered methods, and a
    non-web source link. Checked: wrong token rejected and *not* saved;
    stale saved token handled; tag filter + search; case-insensitive
    match; empty states; list → card → back; junk source link not
    rendered as a link.
  - **Not verified**: the Docker build (no Docker in the dev sandbox — I
    reproduced the web stage's steps from a clean copy, `npm ci` then
    build, and the output was byte-identical to the tested build, and
    confirmed the lockfile carries the Linux native binaries `npm ci` needs
    in the image, but the image itself hasn't been built); anything on a
    real phone (installability, safe-area insets, touch feel); the
    deployed path through the tunnel.
  - Screenshot tooling gotcha: in the emulated phone viewport, captures
    taken *after scrolling* came back stale/tiled even though the DOM was
    correct (checked via `scrollY` and element geometry). A tall viewport
    (375×1500) shows a whole card without scrolling and captured reliably.
- **UI scale — fluid rem, found on a real phone.** The first version was
  sized in fixed `px` and looked tiny on Oscar's phone ("a million items
  on screen"). Cause: that phone lays the page out at ~**1000 CSS px**
  wide (a Chrome zoom/display-size setting; the viewport meta on the
  deployed page was verified correct), so a UI built for ~400px shrank to
  a third. Reproduced by emulating a 980px viewport, where it looked
  identical to the phone's screenshots. Fix: `html { font-size:
  clamp(1rem, 4.7vw, 3rem) }` and **everything sized in `rem`**, so the UI
  is the same proportion of the screen whatever width the browser
  reports. New components must use `rem`, not `px`.
- **Step 2 — done: shopping lists.** A third **Lists** tab, plus a "+" on
  every pantry row, recipe-list card and the recipe card.
  - **"+" → sheet → confirm, never a silent add.** The sheet has a list
    drop-down (starting on the list used last time, else the first — kept
    in `localStorage`, only a convenience), an amount (Each/g/mL chips + a
    stepper) for an item or a servings stepper for a recipe, and an
    explicit Add. "New list…" in the drop-down creates one inline, so an
    empty app isn't a dead end. Recipes go through the existing
    `POST /shopping-lists/{id}/recipes`, so the desktop's rules apply
    unchanged (scaled by servings; tsp/tbsp, unset amounts and
    non-perishables skipped; merge by item + unit + source recipe).
  - **List screen**: lines grouped — loose items first, then one group
    per recipe (heading links to the recipe, "Remove all" for the group);
    a stepper and a remove (✕) per line. Removing always asks first. A
    recipe's lines can be fractional (`1¼` onions for 5 servings of a
    4-serving recipe) — same as the desktop; the stepper then moves by
    whole units from there.
  - **Quantity taps are optimistic**: the number changes immediately, the
    write follows debounced by 400ms (a run of taps is one request) via
    `PATCH /shopping-list-items/{id}/amount`; on any failed write the
    lists are reloaded from the server so the screen can't show something
    unsaved. Step sizes (`shoppingLogic.ts`): count ±1, g/mL ±50, ±100 from
    500 up; never below one step (removal is the explicit action).
  - **Bottom sheet closes on Android Back**: `Sheet.svelte` pushes a
    history entry while open and closes on `popstate` — one path whether
    the user taps outside, Cancel or Back.
  - **Third bulk endpoint**: `GET /shopping` (every list with its lines)
    in `routes/overview.rs`; writes reuse the existing routes. Proxy paths
    for them added to `mobile/vite.config.ts`.
  - **Left out on purpose**: prices/totals and SKU swapping on the phone
    (the desktop's pricing logic isn't ported), renaming/deleting lists,
    and a recipe "×N batches" control (desktop's duplicate-block
    semantics) — add/change quantity/remove was the ask.
  - Verified in a phone-sized browser against the seeded dev server
    (which now seeds a "Weekly Shop" list with a recipe's lines and an
    empty "Costco"): stepper writes reach the server, sheet defaults and
    Android-Back, add item, add recipe at changed servings into a newly
    created list, keep/remove confirmations, remove-all. Pure logic is
    unit-tested (`npm test` in `mobile/`, Node's built-in runner).
    `thin_client.rs` also covers `/shopping`. **Not tested on a real
    phone yet.**
- **Still to do**:
  - Offline: a service worker caching the last-seen pantry/recipes/lists
     for *reading* (grocery stores have bad signal); queued offline writes
     deliberately not planned. This is also where real installability gets
     properly checked on a device — step 1 ships a manifest and icons but
     no service worker.
- **Gotcha that nearly shipped**: `.dockerignore`'s bare `node_modules`
  only matches at the context root, not `mobile/node_modules`, so the
  Windows `node_modules` would have been copied into the Linux build and
  overwritten its install with the wrong native binaries. It's
  `**/node_modules` now, plus `mobile/dist`.
- **Security note**: the shared token will live in one more browser. A
  lost phone means rotating `KAI_SHARED_TOKEN` in the Unraid `.env`, which
  also signs the desktop apps out until the new one is entered.

## Other reference

- Unraid deploy: see personal memory `project_unraid_paths.md` (repo at
  `/mnt/user/appdata/kai/repo`).
