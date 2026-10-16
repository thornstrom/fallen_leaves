"""Skriver rå API-data som newline-delimited JSON till landing-volymen."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable


def write_ndjson(directory: Path | str, name: str, records: Iterable[dict]) -> Path | None:
    """Skriver en post per rad till ``directory/name.json``. Tomma listor ger ingen fil."""
    records = list(records)
    if not records:
        return None

    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{name}.json"
    tmp = path.with_suffix(".json.tmp")
    with tmp.open("w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False))
            f.write("\n")
    # Byt namn först när filen är komplett så att Auto Loader aldrig läser en halvskriven fil.
    tmp.rename(path)
    return path
