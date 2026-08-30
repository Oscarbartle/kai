#!/usr/bin/env bash
# Manual live smoke test against a real running kai-server (e.g. after
# `docker compose up -d`, or `cargo run -p kai-server` with a local Postgres).
# The automated tests (tests/lifecycle.rs, tests/http.rs) already cover this
# same ground against a real embedded Postgres — this script is for poking
# at an actual deployed instance by hand, e.g. once it's live on Unraid.
#
# Usage: BASE_URL=https://kai.yourdomain.com TOKEN=... ./smoke-test.sh
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:8787}"
TOKEN="${TOKEN:?set TOKEN to the server's KAI_SHARED_TOKEN}"

echo "-> GET /health (no auth needed)"
curl -sf "$BASE_URL/health" | tee /dev/stderr | grep -q '"ok":true'
echo

echo "-> GET /items with no token — expect 401"
status=$(curl -s -o /dev/null -w '%{http_code}' "$BASE_URL/items")
[ "$status" = "401" ] || { echo "expected 401, got $status"; exit 1; }
echo "  got 401 as expected"

echo "-> GET /status with the real token — expect 200"
curl -sf -H "Authorization: Bearer $TOKEN" "$BASE_URL/status"
echo

echo "-> POST /items (create 'Smoke Test Item')"
created=$(curl -sf -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
    -d '{"name":"Smoke Test Item"}' "$BASE_URL/items")
echo "$created"
item_id=$(echo "$created" | grep -o '"id":[0-9]*' | head -1 | grep -o '[0-9]*')

echo "-> GET /items (confirm it's listed)"
curl -sf -H "Authorization: Bearer $TOKEN" "$BASE_URL/items" | grep -q "\"id\":$item_id" \
    && echo "  found item $item_id in the list"

echo "-> DELETE /items/$item_id (clean up)"
curl -sf -X DELETE -H "Authorization: Bearer $TOKEN" "$BASE_URL/items/$item_id" -o /dev/null
echo "  deleted"

echo
echo "All checks passed."
