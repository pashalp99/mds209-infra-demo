-- Decision 2 · Staff plan (story 4).
-- Same forecast, different level of detail: the busiest hour of each shift sets the headcount.

CREATE OR REPLACE TABLE mart_staff_plan AS
WITH hourly AS (
    SELECT date, outlet_code, hour, sum(fc_censor_aware) AS portions
    FROM fc_plan
    GROUP BY ALL
),
shifts AS (
    SELECT date, outlet_code,
           CASE WHEN hour < 16 THEN 'AM' ELSE 'PM' END AS shift,
           max(portions)                               AS peak_hour_portions
    FROM hourly
    GROUP BY ALL
),
rostered AS (
    SELECT outlet_code, isodow(roster_date) AS dow, shift, avg(headcount) AS headcount
    FROM mart_roster_daily
    WHERE roster_date > DATE '{as_of}' - INTERVAL {lookback_days} DAY
    GROUP BY ALL
)
SELECT
    s.date,
    strftime(s.date, '%a')                                                        AS day,
    s.outlet_code,
    s.shift,
    round(s.peak_hour_portions, 1)                                                AS peak_hour_portions,
    greatest({min_staff}, CAST(ceil(s.peak_hour_portions / {portions_per_staff_hour}) AS INTEGER))
                                                                                  AS recommended_staff,
    round(r.headcount)                                                            AS currently_rostered
FROM shifts AS s
LEFT JOIN rostered AS r
       ON r.outlet_code = s.outlet_code AND r.dow = isodow(s.date) AND r.shift = s.shift
ORDER BY s.outlet_code, s.shift, s.date;
