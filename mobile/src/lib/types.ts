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
