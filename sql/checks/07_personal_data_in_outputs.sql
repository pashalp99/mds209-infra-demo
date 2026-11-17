-- check: No personal data in clean or mart tables
-- severity: error
-- why: Phone numbers and staff names stay in the raw zone. The forecast never needs them.
SELECT table_name, column_name
FROM information_schema.columns
WHERE (table_name LIKE 'clean_%' OR table_name LIKE 'mart_%')
  AND regexp_matches(lower(column_name), '(phone|staff_name|customer|email|address|nik)');
