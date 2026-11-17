-- check: Days when an ingredient sold out (censored demand)
-- severity: info
-- why: After the sell-out, recorded sales understate demand. The forecast must not learn from those hours.
SELECT outlet_code, ingredient, count(*) AS sold_out_days,
       min(strftime(sold_out_ts, '%H:%M')) AS earliest_sell_out,
       max(strftime(sold_out_ts, '%H:%M')) AS latest_sell_out
FROM clean_stock
WHERE sold_out_ts IS NOT NULL
GROUP BY ALL
ORDER BY sold_out_days DESC;
