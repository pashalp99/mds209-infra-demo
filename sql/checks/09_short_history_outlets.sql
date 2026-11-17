-- check: Outlets with less than 26 weeks of history
-- severity: info
-- why: New outlets are still ramping up. Their past is a weak guide, so plan them with a wider buffer.
SELECT outlet_code, min(date) AS first_day, count(DISTINCT date) AS open_days
FROM mart_demand_hourly
GROUP BY ALL
HAVING count(DISTINCT date) < 26 * 7;
