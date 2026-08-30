-- Postgres schema for Kai's remote mode — mirrors the final shape of
-- src-tauri/src/db/mod.rs's SQLite migrations, adjusted for Postgres
-- dialect. See CLAUDE.md's Phase B notes for the dialect differences
-- (SERIAL/IDENTITY instead of AUTOINCREMENT, native BOOLEAN, citext
-- instead of COLLATE NOCASE, JSONB instead of JSON-as-TEXT, RETURNING id
-- instead of last_insert_rowid()). This is a fresh system, so unlike the
-- SQLite side (21 small appended-only steps as the schema evolved) this
-- starts directly at the current shape in one migration — refinery
-- migrations after this one are appended-only, same rule as the SQLite
-- side, never edit this file once it's shipped anywhere.

CREATE EXTENSION IF NOT EXISTS citext;

CREATE TABLE items (
    id             BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name           TEXT NOT NULL,
    is_perishable  BOOLEAN NOT NULL DEFAULT true,
    image_url      TEXT,
    cheapest_by    TEXT NOT NULL DEFAULT 'total',
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE skus (
    id                       BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    item_id                  BIGINT NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    provider                 TEXT NOT NULL,
    sku                      TEXT NOT NULL,
    name                     TEXT NOT NULL,
    brand                    TEXT,
    variety                  TEXT,
    original_price           DOUBLE PRECISION,
    sale_price               DOUBLE PRECISION,
    is_special               BOOLEAN NOT NULL DEFAULT false,
    save_percentage          DOUBLE PRECISION,
    promotion_start_date     TEXT,
    promotion_end_date       TEXT,
    cup_price                DOUBLE PRECISION,
    cup_measure              TEXT,
    package_type             TEXT,
    volume_size              TEXT,
    unit                     TEXT NOT NULL DEFAULT 'Each',
    quantity_min             DOUBLE PRECISION,
    quantity_max             DOUBLE PRECISION,
    quantity_increment       DOUBLE PRECISION,
    supports_both_units      BOOLEAN NOT NULL DEFAULT false,
    average_weight_per_unit  DOUBLE PRECISION,
    availability_status      TEXT,
    stock_level              BIGINT,
    images                   JSONB NOT NULL DEFAULT '[]',
    allergens                JSONB NOT NULL DEFAULT '[]',
    ingredients              JSONB NOT NULL DEFAULT '[]',
    is_preferred             BOOLEAN NOT NULL DEFAULT false,
    created_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (item_id, provider, sku)
);

CREATE TABLE tags (
    id    BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name  CITEXT NOT NULL UNIQUE,
    emoji TEXT
);

CREATE TABLE item_tags (
    item_id  BIGINT NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    tag_id   BIGINT NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    PRIMARY KEY (item_id, tag_id)
);

CREATE TABLE recipes (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name        TEXT NOT NULL,
    method      TEXT,
    servings    BIGINT,
    source_url  TEXT,
    image_url   TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE recipe_items (
    -- Postgres has no `rowid`-equivalent to sort by for free (unlike the
    -- SQLite side, which orders ingredient lists by insertion order via
    -- `rowid ASC`) — this column exists purely so ingredient order can
    -- still match the order they were added, not alphabetical.
    id         BIGINT GENERATED ALWAYS AS IDENTITY,
    recipe_id  BIGINT NOT NULL REFERENCES recipes(id) ON DELETE CASCADE,
    item_id    BIGINT NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    amount     DOUBLE PRECISION,
    unit       TEXT,
    PRIMARY KEY (recipe_id, item_id)
);

CREATE TABLE recipe_tags (
    recipe_id  BIGINT NOT NULL REFERENCES recipes(id) ON DELETE CASCADE,
    tag_id     BIGINT NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    PRIMARY KEY (recipe_id, tag_id)
);

CREATE TABLE shopping_lists (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name        TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE shopping_list_items (
    id                BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    list_id           BIGINT NOT NULL REFERENCES shopping_lists(id) ON DELETE CASCADE,
    item_id           BIGINT NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    amount            DOUBLE PRECISION,
    unit              TEXT,
    sku_id            BIGINT REFERENCES skus(id) ON DELETE SET NULL,
    source_recipe_id  BIGINT REFERENCES recipes(id) ON DELETE SET NULL,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE settings (
    key    TEXT PRIMARY KEY,
    value  TEXT NOT NULL
);
