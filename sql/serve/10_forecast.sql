-- Baseline forecast: the average of the same weekday and hour over the last few weeks.
-- Deliberately simple. Two versions, side by side:
--   fc_naive         learns from recorded sales, including the zeros after a sell-out
--   fc_censor_aware  first estimates what customers wanted after the sell-out (story 1)

-- Part 1. History with an estimate of true demand for every hour ({table}_history).
CREATE OR REPLACE TABLE {table}_history AS
WITH history AS (
    SELECT *
    FROM mart_demand_hourly
    WHERE date > DATE '{as_of}' - INTERVAL {profile_days} DAY
      AND date <= DATE '{as_of}'
),

-- Step 1. The normal hourly pattern of each item, learned only from days it did NOT sell out
-- (outside Ramadan, when the pattern is completely different).
clean_days AS (
    SELECT outlet_code, item_id, date
    FROM history
    WHERE NOT is_ramadan
    GROUP BY outlet_code, item_id, date
    HAVING NOT bool_or(is_censored) AND sum(portions) > 0
),
profile AS (
    SELECT h.outlet_code, h.item_id, h.hour,
           sum(h.portions) / sum(sum(h.portions)) OVER (PARTITION BY h.outlet_code, h.item_id) AS share
    FROM history AS h
    JOIN clean_days USING (outlet_code, item_id, date)
    GROUP BY h.outlet_code, h.item_id, h.hour
),

-- Step 2. On a sell-out day, scale up what sold before the sell-out using that pattern.
-- Example: 30 portions sold before 19:00, and normally 60% of the day sells before 19:00
-- → the day's demand was about 50, and each censored hour gets its normal share of 50.
sell_out_days AS (
    SELECT h.outlet_code, h.item_id, h.date,
           sum(h.portions) FILTER (WHERE NOT h.is_censored) AS sold_before,
           sum(p.share)    FILTER (WHERE NOT h.is_censored) AS share_before
    FROM history AS h
    JOIN profile AS p USING (outlet_code, item_id, hour)
    GROUP BY h.outlet_code, h.item_id, h.date
    HAVING bool_or(h.is_censored)
)
SELECT
    h.outlet_code, h.item_id, h.date, h.dow, h.hour, h.portions, h.is_censored,
    CASE WHEN h.is_censored AND s.share_before >= 0.2   -- too early a sell-out: too little to scale
         THEN greatest(h.portions, s.sold_before / s.share_before * p.share)
         ELSE h.portions END AS demand_estimate
FROM history AS h
LEFT JOIN profile AS p USING (outlet_code, item_id, hour)
LEFT JOIN sell_out_days AS s USING (outlet_code, item_id, date);

-- Part 2. The forecast itself, from the most recent weeks of that history.
CREATE OR REPLACE TABLE {table} AS
WITH recent AS (
    SELECT *
    FROM {table}_history
    WHERE date > DATE '{as_of}' - INTERVAL {lookback_days} DAY
),
naive AS (
    SELECT outlet_code, item_id, dow, hour, avg(portions) AS f
    FROM recent
    GROUP BY ALL
),
censor_aware AS (
    SELECT outlet_code, item_id, dow, hour, avg(demand_estimate) AS f
    FROM recent
    GROUP BY ALL
),
targets AS (
    SELECT d.date, d.dow, o.outlet_code, m.item_id, h.hour
    FROM dim_date AS d
    JOIN ref_outlets AS o
      ON d.date >= CAST(o.opened_on AS DATE)
    JOIN dim_menu_history AS m
      ON m.is_active AND d.date >= m.valid_from AND (m.valid_to IS NULL OR d.date < m.valid_to)
    CROSS JOIN range({first_hour}, {last_hour} + 1) AS h(hour)
    WHERE d.date > DATE '{as_of}'
      AND d.date <= DATE '{as_of}' + INTERVAL {horizon_days} DAY
      AND NOT d.is_closed
)
SELECT
    t.*,
    coalesce(n.f, 0)        AS fc_naive,
    coalesce(c.f, n.f, 0)   AS fc_censor_aware
FROM targets AS t
LEFT JOIN naive AS n USING (outlet_code, item_id, dow, hour)
LEFT JOIN censor_aware AS c USING (outlet_code, item_id, dow, hour);
