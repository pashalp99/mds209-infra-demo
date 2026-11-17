-- Stock opname. Story 1: sold_out_ts tells us when recorded sales stop meaning demand.
CREATE OR REPLACE TABLE clean_stock AS
SELECT
    CAST(date AS DATE)                AS stock_date,
    outlet_code,
    ingredient,
    unit,
    CAST(opening_qty AS DOUBLE)       AS opening_qty,
    CAST(closing_qty AS DOUBLE)       AS closing_qty,
    CASE WHEN nullif(sold_out_at, '') IS NULL THEN NULL
         ELSE CAST(date || ' ' || sold_out_at || ':00' AS TIMESTAMP) END AS sold_out_ts
FROM read_parquet('{lake}/stock/*.parquet');

-- Roster. Staff names are dropped; a hashed key is enough to count people.
CREATE OR REPLACE TABLE clean_roster AS
SELECT
    CAST(date AS DATE)          AS roster_date,
    outlet_code,
    shift,
    md5(staff_id)               AS staff_key,
    role,
    CAST(hourly_wage AS INTEGER) AS hourly_wage
FROM read_parquet('{lake}/roster/*.parquet');

-- Story 3: the menu changes. Keep every version with the dates it was valid.
CREATE OR REPLACE TABLE dim_menu_history AS
WITH snapshots AS (
    SELECT
        item_code                                                            AS item_id,
        item_name,
        CAST(price AS INTEGER)                                               AS price,
        is_active = 'true'                                                   AS is_active,
        CAST(regexp_extract(_source_file, '(\d{4}-\d{2}-\d{2})', 1) AS DATE) AS valid_from
    FROM read_parquet('{lake}/menu/*.parquet')
)
SELECT *,
       lead(valid_from) OVER (PARTITION BY item_id ORDER BY valid_from) AS valid_to
FROM snapshots;
