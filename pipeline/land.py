"""Layer 02 · Land.

Copies every new export from data/landing/ into data/raw/ exactly as received,
records it in a manifest (when it arrived, its SHA-256 and size) and makes it read-only.
In the airline stack this is the raw zone on Cloud Storage.

Rule: raw is never edited or replaced. If a source sends a corrected file, it must
arrive under a new name; the old one stays, so every past run can be rebuilt.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import stat
import sys
from datetime import datetime

from .config import banner, path


def sha256(file) -> str:
    h = hashlib.sha256()
    with open(file, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    banner("02 Land", "copy exports into the immutable raw zone")
    landing, raw = path("landing"), path("raw")
    if not landing.exists():
        sys.exit("No exports in data/landing/. Run `make capture` first.")
    raw.mkdir(parents=True, exist_ok=True)
    manifest_file = raw / "_manifest.json"
    manifest = json.loads(manifest_file.read_text(encoding="utf-8")) if manifest_file.exists() else {}

    # 1. Nothing already in raw may have changed since it landed.
    for rel, entry in manifest.items():
        if sha256(raw / rel) != entry["sha256"]:
            sys.exit(f"ERROR raw/{rel} was modified after landing. Raw files must never be edited.")

    # 2. Land new files; refuse to replace an existing file with different content.
    new, unchanged, problems = 0, 0, []
    received_at = datetime.now().isoformat(timespec="seconds")
    for file in sorted(landing.rglob("*.csv")):
        rel = file.relative_to(landing).as_posix()
        digest = sha256(file)
        if rel in manifest:
            if manifest[rel]["sha256"] == digest:
                unchanged += 1
            else:
                problems.append(rel)
            continue
        dest = raw / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(file, dest)
        dest.chmod(stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)  # read-only
        with open(file, encoding="utf-8") as f:
            rows = sum(1 for _ in f) - 1
        manifest[rel] = {"received_at": received_at, "sha256": digest, "bytes": file.stat().st_size, "rows": rows}
        new += 1

    manifest_file.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Landed {new} new file(s); {unchanged} already in raw and unchanged. Raw now holds {len(manifest)} files.")
    if problems:
        for rel in problems:
            print(f"ERROR landing/{rel} differs from raw/{rel}, which already landed.")
        sys.exit("Raw is immutable. Ask the source to deliver the correction under a new file name "
                 "(for example *_correction.csv), so the original stays reproducible.")


if __name__ == "__main__":
    main()
