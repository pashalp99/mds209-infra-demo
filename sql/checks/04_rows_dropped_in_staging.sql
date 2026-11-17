-- check: No rows are lost between the lake and staging
-- severity: error
-- why: Every raw row must be accounted for. A silent drop is worse than a loud failure.
WITH lake AS (
    SELECT _source_file, count(*) AS lake_rows
    FROM read_parquet(['{lake}/pos/*.parquet', '{lake}/gofood/*.parquet', '{lake}/grabfood/*.parquet'],
                      union_by_name = true)
    GROUP BY ALL
),
staging AS (
    SELECT _source_file, count(*) AS staging_rows FROM stg_sales_all GROUP BY ALL
)
SELECT l._source_file, l.lake_rows, coalesce(s.staging_rows, 0) AS staging_rows
FROM lake AS l
LEFT JOIN staging AS s USING (_source_file)
WHERE l.lake_rows <> coalesce(s.staging_rows, 0);
