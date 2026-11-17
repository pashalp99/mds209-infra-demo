-- Staging: one table per source, typed and renamed into the same shape.
-- POS timestamps are already in local time (WIB).

CREATE OR REPLACE TABLE stg_sales_pos AS
SELECT
    'pos'                               AS channel,
    order_id,
    outlet_code,
    CAST(order_ts AS TIMESTAMP)         AS order_ts_local,
    item_name                           AS source_item_name,
    CAST(qty AS INTEGER)                AS qty,
    CAST(unit_price AS INTEGER)         AS unit_price,
    _source_file,
    _ingested_at
FROM read_parquet('{lake}/pos/*.parquet');
