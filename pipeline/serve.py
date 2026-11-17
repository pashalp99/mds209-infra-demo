"""Layer 05 · Serve.

Builds the baseline forecast, scores it on last week, turns it into the two decisions
(stock purchase and staff plan), and publishes them as CSV files and one HTML report.
In the airline stack this is BigQuery feeding dashboards.
"""
from __future__ import annotations

import csv
import html
import json
from collections import defaultdict
from datetime import datetime

import duckdb

from .config import CFG, ROOT, banner, path, render
from .dashboard import build as build_dashboard

LAYERS = [
    ("01 Capture", "pipeline/capture.py simulates monthly exports", "Datastream change capture from SQL Server"),
    ("02 Land", "data/raw/ · read-only CSV + manifest", "Raw zone on Cloud Storage"),
    ("03 Store", "data/lake/bronze/ · Parquet + lineage columns", "Apache Iceberg tables"),
    ("04 Transform", "sql/models/ run by DuckDB", "Spark on Dataproc + Dataform"),
    ("05 Serve", "data/warehouse.duckdb + reports/", "BigQuery + dashboards"),
    ("Schedule", "Makefile", "Cloud Composer (Airflow)"),
]


def run_sql(con, name: str, extra: dict[str, str]) -> None:
    con.execute(render((ROOT / "sql" / "serve" / name).read_text(encoding="utf-8"), extra))


def query(con, sql: str):
    cur = con.execute(sql)
    return [d[0] for d in cur.description], cur.fetchall()


def export_csv(con, table: str) -> None:
    columns, rows = query(con, f"SELECT * FROM {table}")
    with open(path("reports") / f"{table.replace('mart_', '')}.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(columns)
        w.writerows(rows)


def table_html(columns, rows) -> str:
    head = "".join(f"<th>{html.escape(str(c))}</th>" for c in columns)
    body = "".join("<tr>" + "".join(f"<td>{html.escape('' if v is None else str(v))}</td>" for v in r) + "</tr>"
                   for r in rows)
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def layer_counts(con) -> list[str]:
    landing = sum(1 for _ in path("landing").rglob("*.csv"))
    raw = len(json.loads((path("raw") / "_manifest.json").read_text(encoding="utf-8")))
    lake = sum(1 for _ in path("lake").rglob("*.parquet"))
    sales = con.execute("SELECT count(*) FROM clean_sales").fetchone()[0]
    mart = con.execute("SELECT count(*) FROM mart_demand_hourly").fetchone()[0]
    tables = con.execute("SELECT count(*) FROM information_schema.tables").fetchone()[0]
    return [f"{landing} export files", f"{raw} files, never edited", f"{lake} Parquet files",
            f"{sales:,} clean sales lines → {mart:,} model rows", f"{tables} tables", "make all"]


def build_report(con, fc: dict) -> str:
    counts = layer_counts(con)
    layers = table_html(["Layer", "In this demo", "In the airline stack", "Now holds"],
                        [(a, b, c, n) for (a, b, c), n in zip(LAYERS, counts)])

    dq = json.loads((path("reports") / "data_quality.json").read_text(encoding="utf-8"))
    dq_rows = [(d["status"], d["check"], d["rows"] if d["rows"] else "", d["why"]) for d in dq]
    dq_table = table_html(["Status", "Check", "Rows", "Why it matters"], dq_rows)

    columns, rows = query(con, "SELECT * FROM mart_backtest")
    duck = dict(zip(columns, next(r for r in rows if r[0] == "Duck dishes")))
    backtest = table_html(
        ["Items", "True demand", "Recorded sales", "Naive forecast", "Censor-aware forecast",
         "Naive bias", "Censor-aware bias", "Naive WAPE", "Censor-aware WAPE"],
        [(r[0], f"{r[1]:,}", f"{r[2]:,}", f"{r[3]:,.0f}", f"{r[4]:,.0f}",
          f"{r[6]:+.1f}%", f"{r[7]:+.1f}%", f"{r[8]:.1f}%", f"{r[9]:.1f}%") for r in rows])

    # Stock plan, pivoted: outlets down, days across.
    _, stock = query(con, "SELECT outlet_code, date, day, recommended_order, current_order "
                          "FROM mart_stock_plan WHERE ingredient = 'bebek' ORDER BY outlet_code, date")
    days = sorted({(r[1], r[2]) for r in stock})
    grid, standing = defaultdict(dict), {}
    for outlet, d, _, rec, cur in stock:
        grid[outlet][d] = rec
        standing[outlet] = cur
    stock_table = table_html(
        ["Outlet", "Standing order"] + [f"{name} {d:%d %b}" for d, name in days],
        [[o, f"{standing[o]:.0f}"] + [grid[o].get(d, "closed") for d, _ in days] for o in sorted(grid)])

    _, staff = query(con, "SELECT outlet_code, shift, date, recommended_staff, currently_rostered "
                          "FROM mart_staff_plan ORDER BY outlet_code, shift, date")
    sgrid = defaultdict(dict)
    for outlet, shift, d, rec, cur in staff:
        delta = "" if cur is None or rec == cur else f" ({'+' if rec > cur else '−'}{abs(rec - int(cur))})"
        sgrid[(outlet, shift)][d] = f"{rec}{delta}"
    staff_table = table_html(
        ["Outlet", "Shift"] + [f"{name} {d:%d %b}" for d, name in days],
        [[o, s] + [sgrid[(o, s)].get(d, "closed") for d, _ in days] for o, s in sorted(sgrid)])

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Weekly plan · Warung Bebek Nusantara (demo)</title>
<style>
  body {{ font-family: system-ui, -apple-system, Segoe UI, sans-serif; background:#f5f2eb; color:#193229;
         margin:0; padding:32px 16px; line-height:1.5; }}
  main {{ max-width:1100px; margin:0 auto; }}
  h1 {{ font-size:32px; margin:0 0 4px; }} h2 {{ font-size:22px; margin:40px 0 8px; }}
  .eyebrow {{ color:#0e7a57; font-weight:600; letter-spacing:.12em; text-transform:uppercase; font-size:13px; }}
  .note {{ color:#4a5d55; max-width:780px; }}
  .callout {{ background:#193229; color:#fff; border-radius:16px; padding:16px 20px; margin:12px 0; max-width:780px; }}
  .scroll {{ overflow-x:auto; }}
  table {{ border-collapse:collapse; background:#fff; border-radius:12px; overflow:hidden; font-size:14px;
          font-variant-numeric:tabular-nums; margin:8px 0; }}
  th {{ background:#193229; color:#fff; text-align:left; padding:8px 12px; white-space:nowrap; }}
  td {{ padding:7px 12px; border-top:1px solid #e8e2d2; vertical-align:top; }}
</style></head><body><main>
<p class="eyebrow">MDS209 infra demo · synthetic data</p>
<h1>Weekly plan for {fc['plan_start']} to {fc['plan_end']}</h1>
<p class="note">Warung Bebek Nusantara is a fictional restaurant group. Every row was generated by
<code>pipeline/capture.py</code>. Built {datetime.now():%d %b %Y %H:%M} by <code>make all</code>.</p>

<h2>1 · The pipeline, layer by layer</h2>
<div class="scroll">{layers}</div>

<h2>2 · Data quality</h2>
<p class="note">FAIL stops the run. WARN is handled but visible. INFO is a fact the forecast must respect.</p>
<div class="scroll">{dq_table}</div>

<h2>3 · Sold out is not low demand (backtest on the week after {fc['backtest_as_of']})</h2>
<div class="callout">Recorded duck sales were {abs(duck['sales_vs_demand_pct'])}% below what customers wanted,
because the duck ran out. A forecast trained on sales underestimates by {abs(duck['naive_bias_pct'])}%.
Estimating the demand after each sell-out cuts that to {abs(duck['censor_aware_bias_pct'])}%.</div>
<div class="scroll">{backtest}</div>
<p class="note">True demand is only known because this is a simulation. In a real project you only see
recorded sales, which is why the sold-out time in the stock opname matters. Both forecasts also miss
the payday lift at the end of the month: the baseline has no calendar features yet.</p>

<h2>4 · Decision 1: duck to order (whole birds)</h2>
<p class="note">Censor-aware forecast × recipe, plus a {round(fc['stock_buffer'] * 100)}% buffer.
The standing order is what each outlet orders today.</p>
<div class="scroll">{stock_table}</div>

<h2>5 · Decision 2: staff per shift</h2>
<p class="note">Recommended headcount, set by the busiest hour of the shift
({fc['portions_per_staff_hour']} portions per person per hour, at least {fc['min_staff_per_shift']}).
In brackets: the change versus the current roster.</p>
<div class="scroll">{staff_table}</div>
</main></body></html>"""


def main() -> None:
    banner("05 Serve", "forecast, decisions and report")
    fc = dict(CFG["forecast"])
    common = {
        "lookback_days": str(fc["lookback_weeks"] * 7),
        "profile_days": str(fc["profile_weeks"] * 7),
        "horizon_days": str(fc["horizon_days"]),
        "truth": path("truth").as_posix(),
        "stock_buffer": str(fc["stock_buffer"]),
        "min_staff": str(fc["min_staff_per_shift"]),
        "portions_per_staff_hour": str(fc["portions_per_staff_hour"]),
    }
    con = duckdb.connect(str(path("warehouse")))
    run_sql(con, "10_forecast.sql", {**common, "table": "fc_backtest", "as_of": fc["backtest_as_of"]})
    run_sql(con, "10_forecast.sql", {**common, "table": "fc_plan", "as_of": fc["plan_as_of"]})
    run_sql(con, "20_backtest.sql", common)
    run_sql(con, "30_stock_plan.sql", {**common, "as_of": fc["plan_as_of"]})
    run_sql(con, "40_staff_plan.sql", {**common, "as_of": fc["plan_as_of"]})
    run_sql(con, "50_dashboard.sql", common)

    fc["plan_start"], fc["plan_end"] = con.execute("SELECT min(date), max(date) FROM fc_plan").fetchone()
    path("reports").mkdir(parents=True, exist_ok=True)
    for table in ("mart_backtest", "mart_stock_plan", "mart_staff_plan"):
        export_csv(con, table)
    report = path("reports") / "report.html"
    report.write_text(build_report(con, fc), encoding="utf-8")
    dashboard = build_dashboard(con, fc)
    con.close()
    print("Wrote reports/dashboard.html (for the business), reports/report.html (for the data team)")
    print("      and backtest.csv, stock_plan.csv, staff_plan.csv.")
    print(f"Open the dashboard with:  open {dashboard.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
