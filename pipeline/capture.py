"""Layer 01 · Capture.

Simulates the client's source systems delivering monthly exports into data/landing/:
POS, GoFood, GrabFood, stock opname, staff roster and POS menu snapshots.
In the airline stack this layer is Datastream reading every change from SQL Server.

All data is synthetic. "Warung Bebek Nusantara" is a fictional brand, and every
name and phone number is generated.

Because this is a simulation, we also know the TRUE demand, including the portions
customers wanted after the duck sold out. It is written to data/_truth/ and used
only to score forecasts. A real project never has this file.
"""
from __future__ import annotations

import argparse
import csv
import math
import random
import shutil
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

from .config import CFG, as_date, banner, path

HOURS = list(range(CFG["opening_hours"]["first"], CFG["opening_hours"]["last"] + 1))
# Share of a normal day's demand in each opening hour (10:00 ... 21:00).
HOUR_WEIGHT = [0.03, 0.06, 0.13, 0.11, 0.05, 0.04, 0.05, 0.09, 0.14, 0.15, 0.10, 0.05]
# During Ramadan lunch collapses and demand piles up around buka puasa.
RAMADAN_HOUR_FACTOR = {10: 0.3, 11: 0.3, 12: 0.3, 13: 0.3, 14: 0.3, 15: 0.8, 16: 0.8,
                       17: 1.9, 18: 1.9, 19: 1.9, 20: 0.9, 21: 0.9}
DOW_FACTOR = [0.9, 0.9, 0.95, 1.0, 1.1, 1.3, 1.25]  # Monday ... Sunday

OUTLETS = {
    # scale: demand vs. the flagship · duck_order: standing daily order in whole birds
    "PNK-01": dict(scale=1.0, duck_order=50, crew=(4, 6), region="Kalimantan Barat"),
    "PNK-02": dict(scale=0.7, duck_order=35, crew=(3, 5), region="Kalimantan Barat"),
    "JKT-01": dict(scale=1.2, duck_order=60, crew=(4, 7), region="Jabodetabek"),
    "TGR-01": dict(scale=0.8, duck_order=34, crew=(3, 5), region="Jabodetabek"),
}

ITEMS = {
    "BG01": dict(pos="Bebek Goreng Paket A", gofood="Paket Bebek Goreng + Nasi", grab="BEBEK GRG PKT A", daily=60, duck=True),
    "BB01": dict(pos="Bebek Bakar Paket A", gofood="Paket Bebek Bakar + Nasi", grab="BEBEK BKR PKT A", daily=25, duck=True),
    "BS01": dict(pos="Bebek Sambal Ijo", gofood="Bebek Sambal Ijo + Nasi", grab="BEBEK SMBL IJO", daily=30, duck=True),
    "AG01": dict(pos="Ayam Goreng Paket", gofood="Paket Ayam Goreng + Nasi", grab="AYAM GRG PKT", daily=50, duck=False),
    "ET01": dict(pos="Es Teh Manis", gofood="Es Teh Manis", grab="ES TEH MANIS", daily=90, duck=False),
}

# POS menu snapshots: the price list changes and one dish is replaced in July.
MENU_SNAPSHOTS = {
    date(2026, 1, 1): {"BG01": (38000, True), "BB01": (40000, True), "AG01": (30000, True), "ET01": (6000, True)},
    date(2026, 7, 1): {"BG01": (40000, True), "BB01": (40000, False), "BS01": (42000, True),
                       "AG01": (32000, True), "ET01": (7000, True)},
}

FIRST_NAMES = ["Adi", "Agus", "Ani", "Bayu", "Dewi", "Dimas", "Eka", "Fajar", "Fitri", "Gita", "Hendra",
               "Indah", "Joko", "Kurnia", "Lestari", "Mega", "Nanda", "Putri", "Rizky", "Sari", "Taufik",
               "Udin", "Wulan", "Yusuf"]
LAST_NAMES = ["Pratama", "Saputra", "Wijaya", "Santoso", "Lestari", "Hidayat", "Nugroho", "Kurniawan",
              "Rahman", "Siregar", "Utami", "Halim"]
ROLES = ["cook", "cashier", "server", "server"]


def read_seed(name: str) -> list[dict[str, str]]:
    with open(path("seeds") / name, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def poisson(rng: random.Random, lam: float) -> int:
    if lam <= 0:
        return 0
    if lam > 30:  # normal approximation is fine for large means
        return max(0, round(rng.gauss(lam, math.sqrt(lam))))
    threshold, k, p = math.exp(-lam), 0, 1.0
    while True:
        p *= rng.random()
        if p <= threshold:
            return k
        k += 1


def write_csv(file: Path, header: list[str], rows: list[list]) -> None:
    file.parent.mkdir(parents=True, exist_ok=True)
    with open(file, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


class Calendar:
    def __init__(self) -> None:
        self.events = [
            (e["event"], date.fromisoformat(e["start_date"]), date.fromisoformat(e["end_date"]),
             e["outlets_closed"].strip().lower() == "true")
            for e in read_seed("calendar_events.csv")
        ]

    def has(self, day: date, word: str) -> bool:
        return any(word.lower() in name.lower() and start <= day <= end for name, start, end, _ in self.events)

    def closed(self, day: date) -> bool:
        return any(closed and start <= day <= end for _, start, end, closed in self.events)


def active_menu(day: date) -> dict[str, int]:
    snapshot = max(d for d in MENU_SNAPSHOTS if d <= day)
    return {item: price for item, (price, active) in MENU_SNAPSHOTS[snapshot].items() if active}


def season_factor(cal: Calendar, region: str, day: date) -> float:
    factor = 1.0
    if cal.has(day, "Mudik"):  # people leave Jakarta for their hometowns
        factor *= 0.75 if region == "Jabodetabek" else 1.05
    if cal.has(day, "Arus balik"):
        factor *= 0.8 if region == "Jabodetabek" else 1.0
    if day.day >= 25 or day.day <= 2:  # payday window
        factor *= 1.1
    return factor


def simulate(force: bool) -> None:
    landing, truth_dir = path("landing"), path("truth")
    marker = landing / ".captured"
    if marker.exists() and not force:
        print("Exports already delivered to data/landing/ (use --force to regenerate).")
        return
    for folder in (landing, truth_dir):
        if folder.exists():
            shutil.rmtree(folder)

    rng = random.Random(CFG["seed"])
    cal = Calendar()
    outlets_seed = {o["outlet_code"]: o for o in read_seed("outlets.csv")}
    assert set(outlets_seed) == set(OUTLETS), "seeds/outlets.csv and capture.py disagree"

    staff_pool = {
        code: [
            (f"{code.replace('-', '')}-S{i:03d}",
             f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}",
             ROLES[i % len(ROLES)],
             rng.randrange(21000, 26500, 500))
            for i in range(1, 17)
        ]
        for code in OUTLETS
    }

    pos, gofood, grab, stock, roster = (defaultdict(list) for _ in range(5))
    truth: list[list] = []
    counters = defaultdict(int)

    day, end = as_date(CFG["start_date"]), as_date(CFG["end_date"])
    while day <= end:
        month = day.strftime("%Y-%m")
        ramadan = cal.has(day, "Ramadan")
        menu = active_menu(day)
        for code, o in OUTLETS.items():
            opened = date.fromisoformat(outlets_seed[code]["opened_on"])
            if day < opened or cal.closed(day):
                continue
            weeks_open = (day - opened).days // 7
            ramp = min(1.0, 0.55 + 0.05 * weeks_open)  # a new outlet takes months to find its customers
            factor = o["scale"] * DOW_FACTOR[day.weekday()] * season_factor(cal, o["region"], day) * ramp
            go_share, grab_share = (0.30, 0.25) if ramadan else (0.25, 0.20)

            duck_left = o["duck_order"] * 2  # portions: one bird makes two portions
            sold_out_at = None
            ayam_sold = 0
            for hour, weight in zip(HOURS, HOUR_WEIGHT):
                if ramadan:
                    weight *= RAMADAN_HOUR_FACTOR[hour]
                demand = {item: poisson(rng, ITEMS[item]["daily"] * factor * weight) for item in menu}
                for item, d in demand.items():
                    truth.append([day.isoformat(), code, item, hour, d])

                sold = dict(demand)
                duck_items = [i for i in demand if ITEMS[i]["duck"]]
                wanted = sum(demand[i] for i in duck_items)
                if wanted > duck_left:  # the duck runs out in this hour
                    tokens = [i for i in duck_items for _ in range(demand[i])]
                    rng.shuffle(tokens)
                    kept = tokens[:duck_left]
                    for i in duck_items:
                        sold[i] = kept.count(i)
                    if sold_out_at is None:
                        sold_out_at = f"{hour:02d}:{int(59 * duck_left / wanted):02d}"
                duck_left -= sum(sold[i] for i in duck_items)
                ayam_sold += sold.get("AG01", 0)

                for item, n in sold.items():
                    price = menu[item]
                    while n > 0:
                        qty = min(n, rng.choice((1, 1, 1, 2, 2, 3)))
                        n -= qty
                        ts = datetime(day.year, day.month, day.day, hour, rng.randrange(60), rng.randrange(60))
                        r = rng.random()
                        if r < go_share:
                            counters["gofood"] += 1
                            gofood[month].append([
                                f"GF-{day:%y%m%d}-{counters['gofood']:06d}",
                                outlets_seed[code]["gofood_merchant_name"],
                                ts.strftime("%Y-%m-%d %H:%M:%S"),
                                ITEMS[item]["gofood"], qty, qty * round(price * 1.2, -3),
                                f"08{rng.randint(11, 99)}{rng.randint(10_000_000, 99_999_999)}",
                            ])
                        elif r < go_share + grab_share:
                            counters["grab"] += 1
                            grab[month].append([
                                f"A-{counters['grab']:08d}",
                                outlets_seed[code]["grabfood_store_id"],
                                (ts - timedelta(hours=7)).strftime("%Y-%m-%dT%H:%M:%SZ"),  # Grab exports in UTC
                                ITEMS[item]["grab"], qty, round(price * 1.2, -3),
                            ])
                        else:
                            counters[code + day.isoformat()] += 1
                            pos[month].append([
                                f"{code.replace('-', '')}-{day:%Y%m%d}-{counters[code + day.isoformat()]:04d}",
                                code, ts.strftime("%Y-%m-%d %H:%M:%S"), ITEMS[item]["pos"], qty, price,
                            ])

            stock[month].append([day.isoformat(), code, "bebek", "ekor", o["duck_order"], duck_left / 2, sold_out_at or ""])
            stock[month].append([day.isoformat(), code, "ayam", "ekor", 40, 40 - ayam_sold * 0.25, ""])

            morning, evening = o["crew"]
            if cal.has(day, "Mudik") or cal.has(day, "Arus balik"):  # staff go home too
                keep = 0.6 if o["region"] == "Jabodetabek" else 0.85
                morning, evening = max(2, round(morning * keep)), max(2, round(evening * keep))
            crew = rng.sample(staff_pool[code], morning + evening)
            for i, (staff_id, name, role, wage) in enumerate(crew):
                shift, start, finish = ("AM", "10:00", "16:00") if i < morning else ("PM", "16:00", "22:00")
                roster[month].append([day.isoformat(), code, shift, start, finish, staff_id, name, role, wage])
        day += timedelta(days=1)

    headers = {
        "pos": ["order_id", "outlet_code", "order_ts", "item_name", "qty", "unit_price"],
        "gofood": ["order_no", "merchant_name", "created_at", "menu_item", "quantity", "gross_amount", "customer_phone"],
        "grabfood": ["booking_id", "store_id", "order_time_utc", "item", "qty", "price"],
        "stock": ["date", "outlet_code", "ingredient", "unit", "opening_qty", "closing_qty", "sold_out_at"],
        "roster": ["date", "outlet_code", "shift", "shift_start", "shift_end", "staff_id", "staff_name", "role", "hourly_wage"],
    }
    files = 0
    for source, prefix, data in (("pos", "pos_sales", pos), ("gofood", "gofood_orders", gofood),
                                 ("grabfood", "grabfood_orders", grab), ("stock", "stock_opname", stock),
                                 ("roster", "roster", roster)):
        for month, rows in sorted(data.items()):
            write_csv(landing / source / f"{prefix}_{month}.csv", headers[source], rows)
            files += 1
    for snapshot, items in MENU_SNAPSHOTS.items():
        write_csv(landing / "menu" / f"menu_snapshot_{snapshot.isoformat()}.csv",
                  ["item_code", "item_name", "price", "is_active"],
                  [[i, ITEMS[i]["pos"], p, str(a).lower()] for i, (p, a) in items.items()])
        files += 1
    write_csv(truth_dir / "true_demand.csv", ["date", "outlet_code", "item_id", "hour", "demand"], truth)
    marker.write_text(datetime.now().isoformat(timespec="seconds"), encoding="utf-8")

    lines = sum(len(v) for d in (pos, gofood, grab) for v in d.values())
    print(f"Delivered {files} export files to data/landing/ ({lines:,} sales lines across POS, GoFood and GrabFood).")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--force", action="store_true", help="regenerate even if exports already exist")
    args = parser.parse_args()
    banner("01 Capture", "source systems deliver their exports")
    simulate(args.force)


if __name__ == "__main__":
    main()
