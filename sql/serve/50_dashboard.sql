-- For the business dashboard: duck sold vs. estimated demand per outlet and day,
-- and what the sell-outs cost at menu prices.

CREATE OR REPLACE TABLE mart_duck_history AS
WITH duck_items AS (
    SELECT DISTINCT item_id FROM ref_recipe WHERE ingredient = 'bebek'
),
daily AS (
    SELECT h.date, h.outlet_code,
           sum(h.portions)                                    AS sold,
           sum(h.demand_estimate)                             AS est_demand,
           sum((h.demand_estimate - h.portions) * m.price)    AS lost_revenue
    FROM fc_plan_history AS h
    JOIN duck_items USING (item_id)
    JOIN dim_menu_history AS m
      ON m.item_id = h.item_id AND h.date >= m.valid_from AND (m.valid_to IS NULL OR h.date < m.valid_to)
    GROUP BY ALL
)
SELECT d.*, strftime(s.sold_out_ts, '%H:%M') AS sold_out_at
FROM daily AS d
LEFT JOIN clean_stock AS s
       ON s.stock_date = d.date AND s.outlet_code = d.outlet_code AND s.ingredient = 'bebek'
ORDER BY d.date, d.outlet_code;
