// The pure rules behind the shopping-list screens, kept apart from the
// components so they can be tested without a browser.

import type { RecipeBookEntry, ShoppingLine } from './types';

/** The only units a shopping line can have (kai-shared's VALID_UNITS). */
export const UNITS = ['count', 'g', 'mL'] as const;
export type Unit = (typeof UNITS)[number];

/** How far one tap of + / − moves an amount: whole items for a count,
 *  50 for weights/volumes, and 100 once it's into the hundreds (nobody
 *  wants ten taps to get from 500g to 1kg). */
export function stepFor(unit: string | null, amount: number): number {
  if (!unit || unit === 'count') return 1;
  return amount >= 500 ? 100 : 50;
}

/** One + / − tap. Never goes below a single step — taking something off
 *  the list is a deliberate, confirmed remove, not a quantity of zero.
 *  An amount that was never set starts at one item. */
export function stepAmount(
  amount: number | null,
  unit: string | null,
  direction: 1 | -1
): { amount: number; unit: string } {
  if (amount == null) return { amount: 1, unit: unit ?? 'count' };
  // Going down from exactly 500 uses the finer step, so 500 → 450 → 400.
  const step = stepFor(unit, direction === -1 ? amount - 1 : amount);
  const next = Math.round((amount + direction * step) * 100) / 100;
  return { amount: Math.max(next, step), unit: unit ?? 'count' };
}

export interface LineGroup {
  /** `null` for lines added one at a time rather than from a recipe. */
  recipeId: number | null;
  name: string | null;
  lines: ShoppingLine[];
}

/** Loose items first, then one group per recipe (in the order each first
 *  appears). A recipe that has since been deleted keeps its lines, under a
 *  neutral heading, rather than losing them. */
export function groupLines(lines: ShoppingLine[], book: RecipeBookEntry[]): LineGroup[] {
  const loose: ShoppingLine[] = [];
  const byRecipe = new Map<number, ShoppingLine[]>();
  for (const line of lines) {
    if (line.source_recipe_id == null) loose.push(line);
    else {
      const bucket = byRecipe.get(line.source_recipe_id) ?? [];
      bucket.push(line);
      byRecipe.set(line.source_recipe_id, bucket);
    }
  }
  const groups: LineGroup[] = [];
  if (loose.length) groups.push({ recipeId: null, name: null, lines: loose });
  for (const [recipeId, group] of byRecipe) {
    const name = book.find((b) => b.recipe.id === recipeId)?.recipe.name ?? 'A removed recipe';
    groups.push({ recipeId, name, lines: group });
  }
  return groups;
}

/** Which list the "add to" sheet should start on: the one used last time
 *  if it still exists, otherwise the first. */
export function defaultListId(listIds: number[], lastUsed: number | null): number | null {
  if (lastUsed != null && listIds.includes(lastUsed)) return lastUsed;
  return listIds[0] ?? null;
}
