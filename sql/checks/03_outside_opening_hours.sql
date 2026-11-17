-- check: All orders fall inside opening hours (10:00–22:00 WIB)
-- severity: error
-- why: Orders at 04:00 usually mean a timezone changed in a source export, not a night shift.
SELECT channel, _source_file, sales_hour, count(*) AS lines
FROM clean_sales
WHERE sales_hour NOT BETWEEN {first_hour} AND {last_hour}
GROUP BY ALL
ORDER BY lines DESC;
