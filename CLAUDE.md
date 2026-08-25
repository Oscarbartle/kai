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
  it.
- Confirm scope before broad or destructive actions (wiping files, deleting
  branches, etc.) even when the direction has been agreed in principle.

## Project state

- `main` — the old Python/PySide6 app, full history preserved, not being
  developed further. Reference it for prior art (see below) but don't build
  on it.
- `v2` — active branch. Bare Tauri + Svelte + TS shell so far (app window
  titled "Kai", no features yet).

## Architecture direction

- **Frontend**: Svelte + TypeScript (chosen for being lightweight, low
  boilerplate, common Tauri pairing).
- **Backend**: Rust, via Tauri commands (`#[tauri::command]`) — rewriting the
  old Python logic rather than porting it as-is.
- **Cross-platform**: macOS + Windows desktop first. Windows builds need a
  Windows machine or CI (can't cross-compile from macOS). Android is possible
  later via Tauri 2.0 mobile support but needs its own init + touch UI work —
  not started.
- **Future idea (not started)**: a second, separate stripped-down companion
  app (e.g. mobile) living in the same repo as `apps/desktop` + `apps/mobile`,
  sharing one backend/API, each with its own `src-tauri`.
- **Auto-update**: deferred. Plan was `tauri-plugin-updater` + a signed
  release manifest; hosting (GitHub Releases vs self-hosted on the Unraid
  box) was not decided — revisit when picked back up.
- **Multi-retailer**: Woolworths NZ only for now, but model things so another
  supermarket can be added later via a settings/provider switch rather than
  hardcoding Woolworths assumptions everywhere.

## Woolworths NZ API (confirmed live, no auth required)

- Search: `GET https://www.woolworths.co.nz/api/v1/products?target=search&search={query}&inStockProductsOnly=false&size={n}`
  → `{"products":{"items":[{sku, name, brand, variety, barcode, price:{...}, size:{cupPrice, cupMeasure, packageType, volumeSize}, images:{small,big}, stockLevel, availabilityStatus, departments:[...]}]}}`
- Product detail: `GET https://www.woolworths.co.nz/api/v1/products/{sku}`
  → richer than search results: adds `genericName`, `breadcrumb`
  (department/aisle/shelf), multiple `images`, `healthStarRating`, `origins`,
  `description`, `allergens`, `claims`, `ingredients`, `nutrition` table, plus
  the same `price`/`size` blocks.
- Old app only used a curated subset (current/original price, cup
  price/measure, promo dates, stock status) — the live API returns much more
  than that if it turns out to be useful (nutrition, allergens, etc).
- Cart-add (`POST /api/v1/trolleys/my/items`) requires the user's real
  browser cookies (Woolworths login) — see `git show main:kai/core/woolworths_cart.py`
  for the old cookie-extraction approach. Not needed for read-only product
  data.

## Prior art worth referencing (on `main`, not carried forward as code)

- `kai/objects/item.py` — old Item model: name, stock_code, cached
  `online_data`, tags, is_long_term, sold_by_weight, default_weight_kg.
- `kai/objects/woolworths_data.py` — old product-fetch + field extraction.
- `kai/objects/price_history.py` — separate price-snapshot store keyed by
  item id, with min/max/avg-in-window helpers.
- `kai/server/` — old FastAPI-ish backend for remote/client-server mode.

## Item domain model (decided, not yet implemented)

- **Item = a concept** the user tracks (e.g. "Milk"), not a single product.
  Holds one or more **linked SKUs** for price comparison. An item can have
  just one SKU if that's all that's relevant.
- **Each linked SKU** caches, from the provider's product API:
  - Identity: `provider` (e.g. `"woolworths"`) + `sku`
  - `name`, `brand`, `variety`
  - `price`: current, original, is-on-special flag, save %
  - `size`: `cupPrice` + `cupMeasure` (price per unit, e.g. $/1L) — this is
    the real cross-SKU comparison metric, not raw price, since SKUs can be
    different pack sizes
  - `availabilityStatus` / `stockLevel`
  - `images`
  - `packageType` / `volumeSize` (human-readable size)
  - `allergens`, `ingredients` — important: Oscar's partner is gluten free,
    so allergen flagging is a real requirement, not a nice-to-have. Woolworths
    returns allergens as a structured list (e.g. `"Contains Milk"`); use that
    directly for badges. Ingredients (free text) is backup for cases the
    allergens list doesn't catch.
  - Nice-to-have, lower priority: `breadcrumb` (department/aisle/shelf — would
    let a shopping list sort itself by aisle later) and
    `promotionStartDate`/`EndDate`
  - Explicitly excluded from v1: `barcode`, `healthStarRating`, `description`,
    `claims`, full `nutrition` table. Easy to add later from the same API
    response if needed — not a re-architecture.
- **Price history is per-SKU only.** Time-series snapshots keyed by SKU, same
  idea as the old `PriceHistory` object. No item-level average and no
  item-level rollup/trend — deliberately rejected. "Did this item get more
  expensive" is answered by looking at individual SKUs' own history, not a
  derived combined metric.
- Not yet decided: whether Item keeps pantry-specific fields from the old
  model (tags, is_long_term, sold_by_weight, default_weight_kg) — open
  question for a future round, not addressed yet.

## Other reference

- Unraid deploy: see personal memory `project_unraid_paths.md` (repo at
  `/mnt/user/appdata/kai/repo`).
