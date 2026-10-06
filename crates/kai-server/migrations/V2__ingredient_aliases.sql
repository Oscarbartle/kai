-- What the recipe importer has learned: "when a recipe says X, it means this
-- pantry item". `alias` is the ingredient's normalised name (lowercase,
-- filler dropped, singular, words sorted), unique case-insensitively; an
-- alias goes with its item, so it can never point at something deleted.
CREATE TABLE ingredient_aliases (
    alias    CITEXT PRIMARY KEY,
    item_id  BIGINT NOT NULL REFERENCES items(id) ON DELETE CASCADE
);
