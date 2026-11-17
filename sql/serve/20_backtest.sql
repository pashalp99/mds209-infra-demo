-- Score last week's forecast against what really happened.
-- SIMULATION ONLY: we know true demand because we generated it. A real project only
-- sees recorded sales, which is exactly why sold-out hours have to be flagged.

CREATE OR REPLACE TABLE mart_backtest AS
WITH truth AS (
    SELECT CAST(date AS DATE) AS date, outlet_code, item_id,
           CAST(hour AS INTEGER) AS hour, CAST(demand AS INTEGER) AS demand
    FROM read_csv('{truth}/true_demand.csv', header = true, all_varchar = true)
),
duck_items AS (
    SELECT DISTINCT item_id FROM ref_recipe WHERE ingredient = 'bebek'
),
daily AS (
    SELECT f.outlet_code, f.item_id, f.date,
           d.item_id IS NOT NULL         AS is_duck,
           sum(coalesce(t.demand, 0))    AS demand,
           sum(coalesce(m.portions, 0))  AS sales,
           sum(f.fc_naive)               AS naive,
           sum(f.fc_censor_aware)        AS aware
    FROM fc_backtest AS f
    LEFT JOIN truth AS t USING (date, outlet_code, item_id, hour)
    LEFT JOIN mart_demand_hourly AS m USING (date, outlet_code, item_id, hour)
    LEFT JOIN duck_items AS d USING (item_id)
    GROUP BY ALL
)
SELECT
    CASE WHEN is_duck THEN 'Duck dishes' ELSE 'Other items' END            AS item_group,
    sum(demand)                                                            AS true_demand,
    sum(sales)                                                             AS recorded_sales,
    round(sum(naive))                                                      AS naive_forecast,
    round(sum(aware))                                                      AS censor_aware_forecast,
    round(100 * (sum(sales) - sum(demand)) / sum(demand), 1)               AS sales_vs_demand_pct,
    round(100 * (sum(naive) - sum(demand)) / sum(demand), 1)               AS naive_bias_pct,
    round(100 * (sum(aware) - sum(demand)) / sum(demand), 1)               AS censor_aware_bias_pct,
    round(100 * sum(abs(naive - demand)) / sum(demand), 1)                 AS naive_wape_pct,
    round(100 * sum(abs(aware - demand)) / sum(demand), 1)                 AS censor_aware_wape_pct
FROM daily
GROUP BY ALL
ORDER BY item_group;
