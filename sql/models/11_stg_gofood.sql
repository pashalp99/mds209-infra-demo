-- GoFood names outlets by merchant name, not by our outlet code.
-- customer_phone is deliberately NOT selected: the forecast does not need it,
-- so it never leaves the raw zone.

CREATE OR REPLACE TABLE stg_sales_gofood AS
SELECT
    'gofood'                                                  AS channel,
    g.order_no                                                AS order_id,
    o.outlet_code,
    CAST(g.created_at AS TIMESTAMP)                           AS order_ts_local,
    g.menu_item                                               AS source_item_name,
    CAST(g.quantity AS INTEGER)                               AS qty,
    CAST(g.gross_amount AS INTEGER) / CAST(g.quantity AS INTEGER) AS unit_price,
    g._source_file,
    g._ingested_at
FROM read_parquet('{lake}/gofood/*.parquet') AS g
LEFT JOIN ref_outlets AS o ON o.gofood_merchant_name = g.merchant_name;
