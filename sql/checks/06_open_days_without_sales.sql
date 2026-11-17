-- check: Every open outlet-day has sales
-- severity: warn
-- why: A missing day is a missing export, not zero demand. Ask the source before modelling it.
SELECT m.outlet_code, m.date
FROM mart_demand_hourly AS m
GROUP BY ALL
HAVING sum(m.portions) = 0
ORDER BY m.date;
