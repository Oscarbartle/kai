// Shared "what does this shopping list line actually cost" logic.
//
// Used by both the Shopping Lists tab's card totals (+page.svelte) and
// ShoppingListDetail's own "SKUs needed" section — they used to compute
// this independently, and drifted: the card summed each line's raw
// sale_price with no regard for amount/unit, so a 450g need against a
// $2.49/kg onion SKU showed $2.49 on the card but the correctly-scaled
// $1.12 on the detail page. Both now call the same function so they
// can't disagree again.

export interface PricingSku {
	id: number;
	price: { sale_price: number | null };
	size: { cup_price: number | null; volume_size: string | null };
	quantity: { unit: string; supports_both_each_and_kg: boolean };
}

export interface PricingLine {
	amount: number | null;
	unit: string | null;
	sku: { id: number } | null;
}

// Narrow, single-source parser for Woolworths' own pack-size labels
// ("700g", "1.5kg", "2L") — confirmed by a live sweep of ~470 products,
// see CLAUDE.md. Only handles the plain <number><unit> shape.
export function parsePackSize(volumeSize: string | null): { grams?: number; mL?: number } | null {
	if (!volumeSize) return null;
	const m = volumeSize.trim().match(/^(\d+(?:\.\d+)?)\s*(kg|g|l|ml)$/i);
	if (!m) return null;
	const value = parseFloat(m[1]);
	const unit = m[2].toLowerCase();
	if (unit === 'kg') return { grams: value * 1000 };
	if (unit === 'g') return { grams: value };
	if (unit === 'l') return { mL: value * 1000 };
	if (unit === 'ml') return { mL: value };
	return null;
}

export interface SkuGroupTotal {
	skuId: number;
	totalPrice: number | null;
}

// Groups lines by chosen SKU and prices each group: count-based lines
// scale by the pack price, g/mL lines against a weight-sold SKU scale by
// the $/kg cup price, and g/mL lines against an each-only SKU convert to
// whole packs (rounded up) via the SKU's own pack-size label first.
// Lines with no SKU chosen contribute nothing — flagged elsewhere, not
// guessed at here.
export function priceSkuGroups(lines: PricingLine[], skuById: Map<number, PricingSku>): SkuGroupTotal[] {
	const bySku = new Map<number, PricingLine[]>();
	for (const line of lines) {
		if (!line.sku) continue;
		const parts = bySku.get(line.sku.id) ?? [];
		parts.push(line);
		bySku.set(line.sku.id, parts);
	}

	const out: SkuGroupTotal[] = [];
	for (const [skuId, parts] of bySku) {
		const sku = skuById.get(skuId);
		if (!sku) continue;

		let totalPrice: number | null = null;
		if (sku.price.sale_price != null) {
			const isWeightSku =
				sku.quantity.unit.toLowerCase() === 'kg' || sku.quantity.supports_both_each_and_kg;

			if (isWeightSku) {
				const prices = parts
					.map((l) => {
						if (l.amount == null) return null;
						if (l.unit === 'count') return sku.price.sale_price! * l.amount;
						if ((l.unit === 'g' || l.unit === 'mL') && sku.size.cup_price != null) {
							return (sku.size.cup_price * l.amount) / 1000;
						}
						return null;
					})
					.filter((p): p is number => p != null);
				totalPrice = prices.length ? prices.reduce((a, b) => a + b, 0) : null;
			} else {
				const countTotal = parts.reduce(
					(sum, p) => sum + (p.unit === 'count' && p.amount != null ? p.amount : 0),
					0
				);
				const gramsTotal = parts.reduce(
					(sum, p) => sum + (p.unit === 'g' && p.amount != null ? p.amount : 0),
					0
				);
				const mlTotal = parts.reduce(
					(sum, p) => sum + (p.unit === 'mL' && p.amount != null ? p.amount : 0),
					0
				);
				const pack = parsePackSize(sku.size.volume_size);
				let convertedPacks = 0;
				if (gramsTotal > 0 && pack?.grams) convertedPacks += Math.ceil(gramsTotal / pack.grams);
				if (mlTotal > 0 && pack?.mL) convertedPacks += Math.ceil(mlTotal / pack.mL);
				const count = countTotal + convertedPacks;
				totalPrice = count > 0 ? sku.price.sale_price * count : null;
			}
		}

		out.push({ skuId, totalPrice });
	}
	return out;
}

export function sumSkuGroupTotals(groups: SkuGroupTotal[]): number | null {
	const prices = groups.map((g) => g.totalPrice).filter((p): p is number => p != null);
	return prices.length ? prices.reduce((a, b) => a + b, 0) : null;
}
