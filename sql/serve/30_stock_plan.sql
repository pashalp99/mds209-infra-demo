-- Decision 1 · Stock purchase (story 4).
-- Forecast portions × recipe = ingredients needed. Order a bit above the forecast,
-- because running out of duck costs more than one leftover bird.

CREATE OR REPLACE TABLE mart_stock_plan AS
WITH need AS (
    SELECT f.date, f.outlet_code, r.ingredient, r.unit,
           sum(f.fc_naive * r.qty_per_portion)        AS naive_need,
           sum(f.fc_censor_aware * r.qty_per_portion) AS forecast_need
    FROM fc_plan AS f
    JOIN ref_recipe AS r USING (item_id)
    GROUP BY ALL
),
standing_order AS (
    SELECT outlet_code, ingredient, median(opening_qty) AS current_order
    FROM clean_stock
    WHERE stock_date > DATE '{as_of}' - INTERVAL {lookback_days} DAY
    GROUP BY ALL
)
SELECT
    n.date,
    strftime(n.date, '%a')                                        AS day,
    n.outlet_code,
    n.ingredient,
    n.unit,
    round(n.naive_need, 1)                                        AS naive_need,
    round(n.forecast_need, 1)                                     AS forecast_need,
    CAST(ceil(n.forecast_need * (1 + {stock_buffer})) AS INTEGER) AS recommended_order,
    s.current_order
FROM need AS n
LEFT JOIN standing_order AS s USING (outlet_code, ingredient)
ORDER BY n.ingredient, n.outlet_code, n.date;
