"""Data checks: fail loudly instead of quietly working around problems.

Each file in sql/checks/ is a query that returns the rows that break a rule.
Its header sets the severity:
  error  stops the pipeline (nothing gets served)
  warn   lets the run continue, but the problem shows in the report
  info   facts the forecast must respect, such as sold-out days
"""
from __future__ import annotations

import json
import sys

import duckdb

from .config import ROOT, banner, path, render


def parse_header(sql: str) -> dict[str, str]:
    meta = {}
    for line in sql.splitlines():
        if line.startswith("-- ") and ":" in line:
            key, value = line[3:].split(":", 1)
            meta[key.strip()] = value.strip()
    return meta


def main() -> None:
    banner("Checks", "does the data deserve to be served?")
    con = duckdb.connect(str(path("warehouse")), read_only=True)
    results, errors = [], 0
    for file in sorted((ROOT / "sql" / "checks").glob("*.sql")):
        sql = file.read_text(encoding="utf-8")
        meta = parse_header(sql)
        severity = meta.get("severity", "error")
        cur = con.execute(render(sql))
        columns = [d[0] for d in cur.description]
        rows = cur.fetchall()
        passed = len(rows) == 0
        status = "PASS" if passed else {"error": "FAIL", "warn": "WARN", "info": "INFO"}[severity]
        if status == "FAIL":
            errors += 1
        print(f"  {status:<4}  {meta.get('check', file.stem)}" + ("" if passed else f"  ({len(rows)} row(s))"))
        if not passed and severity != "info":
            for row in rows[:5]:
                print("          " + ", ".join(f"{c}={v}" for c, v in zip(columns, row)))
        results.append({
            "check": meta.get("check", file.stem), "why": meta.get("why", ""), "severity": severity,
            "status": status, "rows": len(rows),
            "sample": [dict(zip(columns, map(str, r))) for r in rows[:5]],
        })
    con.close()
    path("reports").mkdir(parents=True, exist_ok=True)
    (path("reports") / "data_quality.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    if errors:
        sys.exit(f"\n{errors} check(s) failed. Fix the data or the code before anything is served.")
    print("All blocking checks passed.")


if __name__ == "__main__":
    main()
