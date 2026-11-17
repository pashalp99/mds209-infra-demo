# Live demo script (about 10 minutes)

Before class, once:

```bash
git init -q && git add -A && git commit -qm "Baseline"   # lets you undo the live fixes later
make all                                                 # so .venv exists and nothing downloads on stage
```

Keep the terminal font large and the report open in a browser tab.

## 1 · The happy path (2 min)

```bash
make reset && make all
```

Talk over the output, one layer at a time:
- **Capture:** 52 monthly exports from six systems. “This is the data request arriving.”
- **Land:** copied, hashed, made read-only. “Nobody edits these. Ever.”
- **Store:** Parquet with `_source_file` and `_ingested_at`. “Every row knows where it came from.”
- **Transform:** staging → clean → mart. Point out `clean_sales` vs `mart_demand_hourly` row counts: order lines vs. model grain.
- **Checks:** all PASS, two INFO lines. “Sold-out days are not an error; they are a fact the model must respect.”

Open `reports/dashboard.html`: this is what the outlet and area managers would see.
- Tiles: how many birds to order, staff shifts needed, and what sell-outs cost in the last 4 weeks.
- Click **PNK-01**: in the bottom-right chart, recorded sales flatten at exactly 100 portions, the
  50-bird standing order. Story 1 in one picture.
- Staff per shift: the same forecast, turned into a headcount (story 4).
- “Can we trust these numbers?”: the checks the business never sees fail, but should know ran.

Then `reports/report.html` for the data-team view: the backtest that proves the censor-aware forecast is better.

## 2 · Break it: a renamed dish (3 min)

```bash
make break SCENARIO=rename
```

The run stops at check 01: GrabFood now sends `BBK GORENG PAKET A`, which maps to nothing.
Ask the room: *what would have happened without this check?* (About 900 duck orders quietly vanish
from the forecast, and next week's order is too small.)

Fix it the way you would in real life, in reference data and not in the raw file:

```bash
echo "grabfood,BBK GORENG PAKET A,BG01" >> seeds/menu_alias.csv
make pipeline
```

## 3 · Break it: a silent timezone change (3 min)

```bash
make break SCENARIO=timezone
```

Check 03 fails: hundreds of GoFood orders at 04:00–09:00. Nobody eats bebek goreng at 4 a.m.;
the October export switched to UTC without telling anyone.

The fix is a conversation with the source, then one documented line in `sql/models/11_stg_gofood.sql`:

```sql
    -- GoFood switched to UTC from the October 2026 export (confirmed with the client).
    CAST(g.created_at AS TIMESTAMP)
      + CASE WHEN g._source_file >= 'gofood/gofood_orders_2026-10' THEN INTERVAL 7 HOUR
             ELSE INTERVAL 0 HOUR END                         AS order_ts_local,
```

Then `make pipeline`. Undo the edit afterwards (`git checkout sql/models/11_stg_gofood.sql`).

## 4 · Optional: duplicates and immutability (2 min)

```bash
make break SCENARIO=duplicate   # WARN, run continues: the latest copy wins, but it is visible
make break SCENARIO=overwrite   # land refuses: raw is immutable
```

For `overwrite`, the proper fix is a correction delivered under a new name:

```bash
mv data/landing/pos/pos_sales_2026-10.csv data/landing/pos/pos_sales_2026-10_correction.csv
cp data/raw/pos/pos_sales_2026-10.csv data/landing/pos/ && chmod u+w data/landing/pos/pos_sales_2026-10.csv
make pipeline
```

## Closing line

“Everything you just saw runs on a laptop in ten seconds. The airline version is the same five layers;
each one just had to grow when a real problem forced it.”

Reset afterwards: `git checkout seeds sql && make reset && make all`.
