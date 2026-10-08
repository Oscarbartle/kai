// Labels for the "which SKU should this recipe buy" selector on a recipe's
// ingredient card. Kept apart from the component so the wording is tested.

export interface PinSku {
	id: number;
	name: string;
	is_preferred: boolean;
	size: { volume_size?: string | null };
	price: { sale_price: number | null };
}

/** One option: "500g · $15.25 · Woolworths NZ Beef Mince Grass Fed 5% Fat",
 *  with a ★ in front of the item's starred SKU. The size leads because it's
 *  what tells similar products apart. */
export function pinOptionLabel(
	sku: PinSku,
	sizeOf: (size: PinSku['size']) => string | null,
	nameOf: (name: string) => string = (n) => n
): string {
	const parts = [
		sizeOf(sku.size),
		sku.price.sale_price != null ? `$${sku.price.sale_price.toFixed(2)}` : null,
		nameOf(sku.name)
	].filter(Boolean);
	return `${sku.is_preferred ? '★ ' : ''}${parts.join(' · ')}`;
}

/** What "Auto" means for this item right now, so it isn't a mystery:
 *  its starred SKU if it has one, otherwise the cheapest pick. */
export function autoPickLabel(skus: PinSku[]): string {
	const starred = skus.find((s) => s.is_preferred);
	if (!starred) return 'Auto — cheapest';
	const size = starred.size.volume_size?.trim();
	return size ? `Auto — ★ ${size}` : 'Auto — ★ starred SKU';
}
