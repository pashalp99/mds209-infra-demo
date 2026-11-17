"""Layer 03 · Store.

Turns each raw CSV into a Parquet file in the lake (data/lake/bronze/<source>/),
adding two lineage columns: _source_file and _ingested_at.
In the airline stack this is Iceberg tables on Cloud Storage.

Like Iceberg, nothing is updated in place: new data arrives as new files, and every
column is kept as text. Typing and cleaning happen later, in code you can rerun.
"""
from __future__ import annotations

import json

import duckdb

from .config import banner, path


def main() -> None:
    banner("03 Store", "write raw files to the lake as Parquet")
    raw, lake = path("raw"), path("lake")
    manifest = json.loads((raw / "_manifest.json").read_text(encoding="utf-8"))
    con = duckdb.connect()
    written = skipped = 0
    for rel, entry in sorted(manifest.items()):
        source, name = rel.split("/", 1)
        dest = lake / source / (name.rsplit(".", 1)[0] + ".parquet")
        if dest.exists():
            skipped += 1
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        src = (raw / rel).as_posix().replace("'", "''")
        con.execute(f"""
            COPY (
                SELECT *, '{rel}' AS _source_file, TIMESTAMP '{entry["received_at"]}' AS _ingested_at
                FROM read_csv('{src}', header = true, all_varchar = true)
            ) TO '{dest.as_posix()}' (FORMAT parquet)
        """)
        written += 1
    print(f"Wrote {written} new Parquet file(s) to data/lake/bronze/; {skipped} already there.")


if __name__ == "__main__":
    main()
