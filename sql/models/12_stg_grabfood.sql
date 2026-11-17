-- GrabFood exports timestamps in UTC. Convert to WIB (UTC+7) here, once,
-- so nothing downstream has to remember it.

CREATE OR REPLACE TABLE stg_sales_grabfood AS
SELECT
    'grabfood'                                                          AS channel,
    g.booking_id                                                        AS order_id,
    o.outlet_code,
    strptime(g.order_time_utc, '%Y-%m-%dT%H:%M:%SZ') + INTERVAL 7 HOUR AS order_ts_local,
    g.item                                                              AS source_item_name,
    CAST(g.qty AS INTEGER)                                              AS qty,
    CAST(g.price AS INTEGER)                                            AS unit_price,
    g._source_file,
    g._ingested_at
FROM read_parquet('{lake}/grabfood/*.parquet') AS g
LEFT JOIN ref_outlets AS o ON o.grabfood_store_id = g.store_id;
