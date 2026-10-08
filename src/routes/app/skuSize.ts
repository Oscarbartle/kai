// A SKU's pack size ("500g", "1.5kg", "6pack") is what tells apart
// otherwise identically-named products — three "Beef Mince Grass Fed 5%
// Fat" at 500g, 750g and 1kg — so it is shown as a badge wherever a SKU
// appears. Woolworths' `size.volume_size` is the source; it is missing on
// a few products, and a few have wording instead of a size ("per kg" for
// loose items, "min order 1kg").

/** The text for a SKU's size badge, or `null` when there is none. Only
 *  tidies the wording ("6pack" → "6 pack"); never invents a size. */
export function sizeLabel(size: { volume_size?: string | null } | null | undefined): string | null {
	const raw = size?.volume_size?.trim();
	if (!raw) return null;
	return raw.replace(/^(\d+)\s*pack$/i, '$1 pack');
}
