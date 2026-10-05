// How old a SKU's Woolworths data is, and when that counts as stale.
// `updated_at` is set by the server/db on every fetch or refresh of the
// SKU (and by nothing else), so it is exactly "when did we last ask
// Woolworths". It can be missing/empty — a server from before the field
// existed, or a SKU just fetched in this session — and then there is
// simply no badge rather than a wrong one.

export const STALE_AFTER_DAYS = 14;
const DAY_MS = 86_400_000;

/** Whole days since `updatedAt`, or `null` if unknown/unparseable. */
export function skuAgeDays(updatedAt: string | null | undefined, now: number = Date.now()): number | null {
	if (!updatedAt) return null;
	const t = Date.parse(updatedAt);
	if (Number.isNaN(t)) return null;
	return Math.max(0, Math.floor((now - t) / DAY_MS));
}

export function isStale(updatedAt: string | null | undefined, now: number = Date.now()): boolean {
	const age = skuAgeDays(updatedAt, now);
	return age != null && age >= STALE_AFTER_DAYS;
}

/** The age of the *oldest* SKU in a set, or `null` if none has a known age.
 *  An item is only as current as its stalest SKU: "cheapest" compares all
 *  of them. */
export function oldestAgeDays(
	skus: { updated_at?: string }[],
	now: number = Date.now()
): number | null {
	let oldest: number | null = null;
	for (const s of skus) {
		const age = skuAgeDays(s.updated_at, now);
		if (age != null && (oldest == null || age > oldest)) oldest = age;
	}
	return oldest;
}

/** The stale age to show for a set of SKUs, or `null` when none is stale. */
export function staleAgeDays(skus: { updated_at?: string }[], now: number = Date.now()): number | null {
	const age = oldestAgeDays(skus, now);
	return age != null && age >= STALE_AFTER_DAYS ? age : null;
}
