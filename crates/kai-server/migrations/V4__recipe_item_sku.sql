-- A SKU pinned to a recipe's ingredient: lines added from the recipe use it,
-- ahead of the item's starred SKU and the cheapest-pick. Cleared if that SKU
-- is deleted.
ALTER TABLE recipe_items ADD COLUMN sku_id BIGINT REFERENCES skus(id) ON DELETE SET NULL;
