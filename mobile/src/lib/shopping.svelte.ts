// Shopping-list state and the writes against it. Module-level reactive
// state, so every screen (Lists tab, list detail, the add sheet) reads the
// same lists without props being threaded through the whole app.
//
// Quantity taps are optimistic: the number changes under the finger at
// once and the server write follows (debounced, so a run of taps is one
// request). If a write fails the lists are reloaded from the server, so
// the screen never keeps showing something that isn't really saved.

import { AuthError, apiGet, apiSend } from './api';
import type { ShoppingEntry, ShoppingList } from './types';

const LAST_LIST_KEY = 'kai.lastList';
const QUANTITY_DEBOUNCE_MS = 400;

export const shopping = $state<{ entries: ShoppingEntry[] | null; toast: string | null }>({
  entries: null,
  toast: null,
});

// App registers this so a rejected token from a write behaves like one
// from a read: back to the token screen.
let onAuthFailed: () => void = () => {};
export function setAuthFailedHandler(fn: () => void) {
  onAuthFailed = fn;
}

let toastTimer: ReturnType<typeof setTimeout> | undefined;
export function showToast(message: string) {
  shopping.toast = message;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => (shopping.toast = null), 3200);
}

function fail(e: unknown) {
  if (e instanceof AuthError) onAuthFailed();
  else showToast(e instanceof Error ? e.message : String(e));
}

export function getLastListId(): number | null {
  try {
    const raw = localStorage.getItem(LAST_LIST_KEY);
    return raw ? Number(raw) : null;
  } catch {
    return null;
  }
}

function rememberList(id: number) {
  try {
    localStorage.setItem(LAST_LIST_KEY, String(id));
  } catch {
    /* only a convenience */
  }
}

export async function loadShopping(): Promise<void> {
  shopping.entries = await apiGet<ShoppingEntry[]>('/shopping');
}

/** Reload after a failed write; its own failure is already being reported. */
async function resync() {
  try {
    await loadShopping();
  } catch (e) {
    fail(e);
  }
}

export async function createList(name: string): Promise<ShoppingList> {
  const list = await apiSend<ShoppingList>('POST', '/shopping-lists', { name });
  shopping.entries = [...(shopping.entries ?? []), { list, lines: [] }];
  return list;
}

export async function addItem(listId: number, itemId: number, amount: number, unit: string): Promise<void> {
  await apiSend('POST', `/shopping-lists/${listId}/items`, { item_id: itemId, amount, unit });
  rememberList(listId);
  await loadShopping();
}

export async function addRecipe(listId: number, recipeId: number, servings: number | null): Promise<void> {
  await apiSend('POST', `/shopping-lists/${listId}/recipes`, {
    recipe_id: recipeId,
    target_servings: servings,
  });
  rememberList(listId);
  await loadShopping();
}

const pendingAmounts = new Map<number, ReturnType<typeof setTimeout>>();

/** Sets a line's quantity: on screen now, saved shortly after. */
export function setLineAmount(lineId: number, amount: number, unit: string) {
  for (const entry of shopping.entries ?? []) {
    const line = entry.lines.find((l) => l.id === lineId);
    if (line) {
      line.amount = amount;
      line.unit = unit;
    }
  }
  clearTimeout(pendingAmounts.get(lineId));
  pendingAmounts.set(
    lineId,
    setTimeout(async () => {
      pendingAmounts.delete(lineId);
      try {
        await apiSend('PATCH', `/shopping-list-items/${lineId}/amount`, { amount, unit });
      } catch (e) {
        fail(e);
        await resync();
      }
    }, QUANTITY_DEBOUNCE_MS)
  );
}

/** Removes lines (one, or all of a recipe's) — gone from the screen at
 *  once, restored from the server if any delete fails. */
export async function removeLines(listId: number, lineIds: number[]): Promise<void> {
  const entry = shopping.entries?.find((e) => e.list.id === listId);
  if (entry) entry.lines = entry.lines.filter((l) => !lineIds.includes(l.id));
  for (const id of lineIds) clearTimeout(pendingAmounts.get(id));
  try {
    await Promise.all(lineIds.map((id) => apiSend('DELETE', `/shopping-list-items/${id}`)));
  } catch (e) {
    fail(e);
    await resync();
  }
}
