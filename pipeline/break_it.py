"""Break the data on purpose, for the live demo.

Each scenario is something that really happens with client exports.
Run through `make break SCENARIO=<name>`, which rebuilds everything from scratch.

  rename     GrabFood renames a dish in the October export          → check 01 fails
  timezone   GoFood silently switches its October export to UTC     → check 03 fails
  duplicate  The POS team re-sends October as a second file         → check 05 warns, run continues
  overwrite  Someone "fixes" an export that already landed in raw   → land refuses
"""
from __future__ import annotations

import csv
import shutil
import sys
from datetime import datetime, timedelta

from .config import banner, path


def rewrite(file, change) -> int:
    with open(file, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    fields = list(rows[0].keys())
    changed = sum(1 for row in rows if change(row))
    with open(file, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    return changed


def rename(row) -> bool:
    if row["item"] == "BEBEK GRG PKT A":
        row["item"] = "BBK GORENG PAKET A"
        return True
    return False


def to_utc(row) -> bool:
    ts = datetime.strptime(row["created_at"], "%Y-%m-%d %H:%M:%S") - timedelta(hours=7)
    row["created_at"] = ts.strftime("%Y-%m-%d %H:%M:%S")
    return True


def edit_qty(row) -> bool:
    if row["order_id"].endswith("-0001"):
        row["qty"] = str(int(row["qty"]) + 1)
        return True
    return False


def main() -> None:
    scenario = sys.argv[1] if len(sys.argv) > 1 else ""
    landing = path("landing")
    banner("Break it", scenario or "?")
    if scenario == "rename":
        n = rewrite(landing / "grabfood" / "grabfood_orders_2026-10.csv", rename)
        print(f"GrabFood now calls 'BEBEK GRG PKT A' 'BBK GORENG PAKET A' ({n} lines in October).")
    elif scenario == "timezone":
        n = rewrite(landing / "gofood" / "gofood_orders_2026-10.csv", to_utc)
        print(f"GoFood's October export is now in UTC, with no warning ({n} lines).")
    elif scenario == "duplicate":
        src = landing / "pos" / "pos_sales_2026-10.csv"
        shutil.copy2(src, src.with_name("pos_sales_2026-10_resend.csv"))
        print("The POS team re-sent October as pos_sales_2026-10_resend.csv.")
    elif scenario == "overwrite":
        n = rewrite(landing / "pos" / "pos_sales_2026-10.csv", edit_qty)
        print(f"Someone edited {n} quantities in the October POS export after it had landed.")
    else:
        sys.exit("Usage: make break SCENARIO=rename|timezone|duplicate|overwrite")


if __name__ == "__main__":
    main()
