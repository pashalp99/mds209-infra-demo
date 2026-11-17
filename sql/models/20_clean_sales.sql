-- All channels in one shape, before any fixing. Checks compare this with the lake.
CREATE OR REPLACE TABLE stg_sales_all AS
SELECT * FROM stg_sales_pos
UNION ALL BY NAME SELECT * FROM stg_sales_gofood
UNION ALL BY NAME SELECT * FROM stg_sales_grabfood;

-- Clean sales: one row per order line, with our own item ID.
-- If a source re-sends a file, keep the most recently ingested copy of each line.
-- Unmapped item names keep a NULL item_id, so a check can catch them.
CREATE OR REPLACE TABLE clean_sales AS
WITH deduplicated AS (
    SELECT *
    FROM stg_sales_all
    QUALIFY row_number() OVER (
        PARTITION BY channel, order_id, source_item_name
        ORDER BY _ingested_at DESC, _source_file DESC
    ) = 1
)
SELECT
    s.channel,
    s.order_id,
    s.outlet_code,
    s.order_ts_local,
    CAST(s.order_ts_local AS DATE) AS sales_date,
    hour(s.order_ts_local)         AS sales_hour,
    s.source_item_name,
    a.item_id,
    s.qty,
    s.unit_price,
    s.qty * s.unit_price           AS revenue,
    s._source_file
FROM deduplicated AS s
LEFT JOIN ref_menu_alias AS a
       ON a.channel = s.channel AND a.source_item_name = s.source_item_name;
