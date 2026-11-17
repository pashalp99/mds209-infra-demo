-- The model table. One row = one outlet × item × date × opening hour.
-- Hours with no sales get 0, but hours after a sold-out are flagged as censored:
-- their 0 means "nothing left to sell", not "nobody wanted it".

CREATE OR REPLACE TABLE mart_demand_hourly AS
WITH grid AS (
    SELECT d.date, d.dow, d.is_ramadan, d.is_payday_window, o.outlet_code, m.item_id, h.hour
    FROM dim_date AS d
    JOIN ref_outlets AS o
      ON d.date >= CAST(o.opened_on AS DATE)
    JOIN dim_menu_history AS m
      ON m.is_active AND d.date >= m.valid_from AND (m.valid_to IS NULL OR d.date < m.valid_to)
    CROSS JOIN range({first_hour}, {last_hour} + 1) AS h(hour)
    WHERE NOT d.is_closed AND d.date <= DATE '{end_date}'
),
sales AS (
    SELECT sales_date, outlet_code, item_id, sales_hour, sum(qty) AS portions
    FROM clean_sales
    WHERE item_id IS NOT NULL
    GROUP BY ALL
),
sold_out AS (
    SELECT s.stock_date, s.outlet_code, r.item_id, hour(s.sold_out_ts) AS sold_out_hour
    FROM clean_stock AS s
    JOIN ref_recipe AS r ON r.ingredient = s.ingredient
    WHERE s.sold_out_ts IS NOT NULL
)
SELECT
    g.*,
    coalesce(s.portions, 0)                                         AS portions,
    coalesce(so.sold_out_hour IS NOT NULL AND g.hour >= so.sold_out_hour, false) AS is_censored
FROM grid AS g
LEFT JOIN sales AS s
       ON s.sales_date = g.date AND s.outlet_code = g.outlet_code
      AND s.item_id = g.item_id AND s.sales_hour = g.hour
LEFT JOIN sold_out AS so
       ON so.stock_date = g.date AND so.outlet_code = g.outlet_code AND so.item_id = g.item_id;

-- Staffing as rostered, per outlet, day and shift. No names, only counts and cost.
CREATE OR REPLACE TABLE mart_roster_daily AS
SELECT
    roster_date,
    outlet_code,
    shift,
    count(DISTINCT staff_key)   AS headcount,
    sum(hourly_wage * 6)        AS labour_cost
FROM clean_roster
GROUP BY ALL;
