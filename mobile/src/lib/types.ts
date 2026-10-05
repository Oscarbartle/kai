// Wire shapes, matching kai-shared (Rust) and what kai-server's /pantry and
// /recipe-book actually return. Only the fields this app reads.

export interface Tag {
  id: number;
  name: string;
  emoji: string | null;
}

export interface Item {
  id: number;
  name: string;
  is_perishable: boolean;
  image_url: string | null;
}

export interface StoredSku {
  id: number;
  item_id: number;
  price: {
    original_price: number | null;
    sale_price: number | null;
    is_special: boolean;
  };
  images: string[];
  /** When Woolworths was last asked about this SKU (UTC, RFC 3339). */
  updated_at?: string;
}

export interface PantryEntry {
  item: Item;
  skus: StoredSku[];
  tags: Tag[];
}

export interface Recipe {
  id: number;
  name: string;
  method: string | null;
  servings: number | null;
  source_url: string | null;
  image_url: string | null;
}

export interface Ingredient {
  item_id: number;
  name: string;
  amount: number | null;
  unit: string | null;
}

export interface RecipeBookEntry {
  recipe: Recipe;
  tags: Tag[];
  ingredients: Ingredient[];
}

export interface ShoppingList {
  id: number;
  name: string;
}

export interface ShoppingLine {
  id: number;
  item_id: number;
  item_name: string;
  amount: number | null;
  unit: string | null;
  /** Which recipe this line came from, if any. */
  source_recipe_id: number | null;
}

export interface ShoppingEntry {
  list: ShoppingList;
  lines: ShoppingLine[];
}

/** What the add-to-list sheet is adding. */
export type AddTarget =
  | { kind: 'item'; itemId: number; name: string }
  | { kind: 'recipe'; recipeId: number; name: string; servings: number | null };
