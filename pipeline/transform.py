"""Layer 04 · Transform.

Runs the SQL models in sql/models/ in file-name order against the warehouse
(data/warehouse.duckdb): staging → clean → mart.
In the airline stack this is Spark and Dataform, scheduled by Cloud Composer.

Each model is one plain SQL file you can read, review in Git and rerun.
"""
from __future__ import annotations

import re
import time

import duckdb

from .config import ROOT, banner, path, render


def main() -> None:
    banner("04 Transform", "staging → clean → mart, in SQL")
    path("warehouse").parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(path("warehouse")))
    for file in sorted((ROOT / "sql" / "models").glob("*.sql")):
        sql = file.read_text(encoding="utf-8")
        started = time.perf_counter()
        con.execute(render(sql))
        tables = re.findall(r"CREATE OR REPLACE TABLE\s+(\w+)", sql, flags=re.IGNORECASE)
        counts = ", ".join(f"{t} {con.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0]:,}" for t in tables)
        print(f"  {file.name:<32} {counts}  ({time.perf_counter() - started:.1f}s)")
    con.close()


if __name__ == "__main__":
    main()
