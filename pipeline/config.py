"""Settings live in config/pipeline.json, not in code."""
from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CFG = json.loads((ROOT / "config" / "pipeline.json").read_text(encoding="utf-8"))


def path(key: str) -> Path:
    return ROOT / CFG["paths"][key]


def as_date(value: str) -> date:
    return date.fromisoformat(value)


def sql_params() -> dict[str, str]:
    """Values substituted into {placeholders} in the SQL files."""
    fc = CFG["forecast"]
    end = as_date(CFG["end_date"])
    return {
        "lake": path("lake").as_posix(),
        "seeds": path("seeds").as_posix(),
        "start_date": CFG["start_date"],
        "end_date": CFG["end_date"],
        "calendar_end": (end + timedelta(days=fc["horizon_days"] + 7)).isoformat(),
        "first_hour": str(CFG["opening_hours"]["first"]),
        "last_hour": str(CFG["opening_hours"]["last"]),
    }


def render(sql: str, extra: dict[str, str] | None = None) -> str:
    params = {**sql_params(), **(extra or {})}
    for key, value in params.items():
        sql = sql.replace("{" + key + "}", value)
    return sql


def banner(layer: str, text: str) -> None:
    print(f"\n== {layer} · {text}")
