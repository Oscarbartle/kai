-- One row per SKU per fetch — the dots on an item's price-history chart.
-- Seeded with each existing SKU's current price, dated by when it was last
-- fetched, so no chart starts empty. A SKU's history goes with it.
CREATE TABLE sku_price_history (
    id             BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    sku_id         BIGINT NOT NULL REFERENCES skus(id) ON DELETE CASCADE,
    recorded_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    sale_price     DOUBLE PRECISION,
    original_price DOUBLE PRECISION,
    is_special     BOOLEAN NOT NULL DEFAULT false,
    cup_price      DOUBLE PRECISION
);
CREATE INDEX idx_sku_price_history_sku ON sku_price_history (sku_id, recorded_at);

INSERT INTO sku_price_history (sku_id, recorded_at, sale_price, original_price, is_special, cup_price)
SELECT id, COALESCE(updated_at, now()), sale_price, original_price, is_special, cup_price
FROM skus;
