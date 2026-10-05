// How old a SKU's Woolworths data is, and when that counts as stale.
// `updated_at` is set by the server on every fetch or refresh of a SKU
// (and by nothing else), so it is exactly "when did we last ask
// Woolworths". It can be missing — a server from before the field
// existed — and then there is no badge rather than a wrong one.
// (Same rule as the desktop app's skuFreshness.ts.)

export const STALE_AFTER_DAYS = 14;
const DAY_MS = 86_400_000;

/** Whole days since `updatedAt`, or `null` if unknown/unparseable. */
export function skuAgeDays(updatedAt: string | null | undefined, now: number = Date.now()): number | null {
  if (!updatedAt) return null;
  const t = Date.parse(updatedAt);
  if (Number.isNaN(t)) return null;
  return Math.max(0, Math.floor((now - t) / DAY_MS));
}

/** The age of the *oldest* SKU in a set if it is 14+ days old, else
 *  `null`. An item is only as current as its stalest SKU, because
 *  "cheapest" compares all of them. */
export function staleAgeDays(
  skus: { updated_at?: string }[],
  now: number = Date.now()
): number | null {
  let oldest: number | null = null;
  for (const s of skus) {
    const age = skuAgeDays(s.updated_at, now);
    if (age != null && (oldest == null || age > oldest)) oldest = age;
  }
  return oldest != null && oldest >= STALE_AFTER_DAYS ? oldest : null;
}
