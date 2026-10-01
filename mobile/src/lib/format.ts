import type { Ingredient, PantryEntry, StoredSku } from './types';

// Same rules as the desktop's Pantry cards (+page.svelte): cheapest by
// plain sale price, and a user-set image beats a SKU's.
export function cheapestSku(skus: StoredSku[]): StoredSku | null {
  const priced = skus.filter((s) => s.price.sale_price != null);
  if (!priced.length) return null;
  return priced.reduce((min, s) => (s.price.sale_price! < min.price.sale_price! ? s : min));
}

export function itemImage(entry: PantryEntry): string | null {
  if (entry.item.image_url) return entry.item.image_url;
  return entry.skus.find((s) => s.images[0])?.images[0] ?? null;
}

export function money(n: number): string {
  return `$${n.toFixed(2)}`;
}

const FRACTIONS: [number, string][] = [
  [0.25, '¼'],
  [1 / 3, '⅓'],
  [0.5, '½'],
  [2 / 3, '⅔'],
  [0.75, '¾'],
];

/** 0.5 → "½", 1.5 → "1½", 200 → "200", 0.4 → "0.4" — recipes read better
 *  with fractions than with decimals, especially for tsp/tbsp. */
export function formatAmount(n: number): string {
  const whole = Math.floor(n);
  const frac = n - whole;
  if (frac < 0.005) return String(whole);
  for (const [value, glyph] of FRACTIONS) {
    if (Math.abs(frac - value) < 0.02) return whole > 0 ? `${whole}${glyph}` : glyph;
  }
  return String(Math.round(n * 100) / 100);
}

/** What an ingredient's quantity column shows. A `count` is just the
 *  number ("2 Brown Onion"); everything else carries its unit. An
 *  ingredient with no amount set shows no quantity at all. */
export function formatQuantity(ing: Ingredient): string {
  if (ing.amount == null) return '';
  const amount = formatAmount(ing.amount);
  return !ing.unit || ing.unit === 'count' ? amount : `${amount} ${ing.unit}`;
}

/** A recipe's method is one freeform text box. People write it one step
 *  per line, sometimes already numbered ("1. Mix…"), sometimes not — so
 *  split on lines, drop any numbering they typed (we number steps
 *  ourselves, otherwise it'd read "1. 1. Mix…"), and only treat it as a
 *  list when there's more than one. A single block stays a paragraph. */
export function methodSteps(method: string | null): string[] {
  if (!method) return [];
  return method
    .split(/\r?\n/)
    .map((line) => line.trim().replace(/^\d+[.)]\s*/, ''))
    .filter((line) => line.length > 0);
}
