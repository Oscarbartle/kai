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

## Other reference

- Unraid deploy: see personal memory `project_unraid_paths.md` (repo at
  `/mnt/user/appdata/kai/repo`).
