"""The business dashboard: the same weekly plan as report.html, for the people who act on it.

Writes reports/dashboard.html, one self-contained file (no internet needed): the data is
embedded as JSON and drawn in the browser by pipeline/templates/dashboard.html.
"""
from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from .config import ROOT, path


def rows(con, sql: str) -> list[dict]:
    cur = con.execute(sql)
    columns = [d[0] for d in cur.description]
    return [dict(zip(columns, r)) for r in cur.fetchall()]


def encode(value):
    if isinstance(value, Decimal):
        return float(value)
    return str(value)


def build(con, fc: dict) -> Path:
    checks = json.loads((path("reports") / "data_quality.json").read_text(encoding="utf-8"))
    data = {
        "meta": {
            "brand": "Warung Bebek Nusantara",
            "as_of": fc["plan_as_of"],
            "plan_start": str(fc["plan_start"]),
            "plan_end": str(fc["plan_end"]),
            "stock_buffer": fc["stock_buffer"],
            "built": datetime.now().strftime("%d %b %Y %H:%M"),
        },
        "outlets": rows(con, "SELECT outlet_code AS code, outlet_name AS name, city FROM ref_outlets ORDER BY 1"),
        "days": [r["date"] for r in rows(con, "SELECT DISTINCT strftime(date, '%Y-%m-%d') AS date FROM fc_plan ORDER BY 1")],
        "stock": rows(con, """
            SELECT strftime(date, '%Y-%m-%d') AS date, outlet_code AS outlet,
                   recommended_order AS recommended, current_order AS standing, forecast_need AS need
            FROM mart_stock_plan WHERE ingredient = 'bebek'"""),
        "staff": rows(con, """
            SELECT strftime(date, '%Y-%m-%d') AS date, outlet_code AS outlet, shift,
                   recommended_staff AS recommended, currently_rostered AS rostered
            FROM mart_staff_plan"""),
        "hourly": rows(con, """
            SELECT strftime(date, '%Y-%m-%d') AS date, outlet_code AS outlet, hour,
                   round(sum(fc_censor_aware), 1) AS portions
            FROM fc_plan GROUP BY ALL ORDER BY ALL"""),
        "history": rows(con, """
            SELECT strftime(date, '%Y-%m-%d') AS date, outlet_code AS outlet, sold,
                   round(est_demand, 1) AS est, round(lost_revenue) AS lost_rp, sold_out_at AS sold_out
            FROM mart_duck_history"""),
        "checks": [{"status": c["status"], "check": c["check"], "rows": c["rows"]} for c in checks],
    }
    template = (ROOT / "pipeline" / "templates" / "dashboard.html").read_text(encoding="utf-8")
    payload = json.dumps(data, default=encode).replace("</", "<\\/")
    out = path("reports") / "dashboard.html"
    out.write_text(template.replace("__DASHBOARD_DATA__", payload), encoding="utf-8")
    return out
