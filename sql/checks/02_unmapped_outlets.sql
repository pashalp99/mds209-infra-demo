-- check: Every sales line belongs to a known outlet
-- severity: error
-- why: Delivery apps name outlets their own way. A renamed merchant must be added to seeds/outlets.csv.
SELECT channel, _source_file, count(*) AS lines
FROM stg_sales_all
WHERE outlet_code IS NULL
GROUP BY ALL;
