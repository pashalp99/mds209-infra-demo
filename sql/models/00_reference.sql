-- Reference data the team maintains by hand, versioned in Git (seeds/*.csv).
-- Story 2: the menu alias table is what makes five sources agree on one dish.

CREATE OR REPLACE TABLE ref_outlets AS
SELECT * FROM read_csv('{seeds}/outlets.csv', header = true, all_varchar = true);

CREATE OR REPLACE TABLE ref_menu_alias AS
SELECT * FROM read_csv('{seeds}/menu_alias.csv', header = true, all_varchar = true);

CREATE OR REPLACE TABLE ref_recipe AS
SELECT item_id, ingredient, unit, CAST(qty_per_portion AS DOUBLE) AS qty_per_portion
FROM read_csv('{seeds}/recipe.csv', header = true, all_varchar = true);

CREATE OR REPLACE TABLE ref_calendar_events AS
SELECT event,
       CAST(start_date AS DATE) AS start_date,
       CAST(end_date AS DATE) AS end_date,
       lower(outlets_closed) = 'true' AS outlets_closed
FROM read_csv('{seeds}/calendar_events.csv', header = true, all_varchar = true);

-- One row per day, with the calendar facts a forecast needs.
CREATE OR REPLACE TABLE dim_date AS
WITH days AS (
    SELECT CAST(d AS DATE) AS date
    FROM range(DATE '{start_date}', DATE '{calendar_end}' + INTERVAL 1 DAY, INTERVAL 1 DAY) AS t(d)
)
SELECT
    d.date,
    isodow(d.date) AS dow,                                   -- 1 = Monday
    strftime(d.date, '%a') AS day_name,
    day(d.date) >= 25 OR day(d.date) <= 2 AS is_payday_window,
    EXISTS (SELECT 1 FROM ref_calendar_events e
            WHERE e.event = 'Ramadan' AND d.date BETWEEN e.start_date AND e.end_date) AS is_ramadan,
    EXISTS (SELECT 1 FROM ref_calendar_events e
            WHERE e.outlets_closed AND d.date BETWEEN e.start_date AND e.end_date) AS is_closed
FROM days d;
