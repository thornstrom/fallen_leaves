"""Hämtar data från källornas API:er och skriver rå JSON till landing-volymen."""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Sequence

from fallen_leaves.config import Layout
from fallen_leaves.sources import http, smhi, trafikverket
from fallen_leaves.sources.landing import write_ndjson

log = logging.getLogger(__name__)


def _run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def ingest_trafikverket(
    layout: Layout,
    api_key: str,
    run_date: date,
    lookback_days: int,
    operators: Sequence[str],
) -> int:
    """Hämtar tåglägen för avgångsdagarna run_date-1 … run_date-lookback_days samt alla driftplatser.

    Flera dagar bakåt hämtas så att nattåg och sena rättningar kommer med; dubbletter hanteras i silver.
    """
    s = http.session()
    run_id = _run_id()
    total = 0

    for offset in range(1, lookback_days + 1):
        day = run_date - timedelta(days=offset)
        target = Path(layout.landing_dir("trafikverket_train_announcement")) / f"departure_date={day.isoformat()}"
        for i, page in enumerate(trafikverket.fetch_announcements(s, api_key, day, operators)):
            write_ndjson(target, f"{run_id}-p{i:04d}", page)
            total += len(page)
        log.info("Trafikverket %s: klart", day)

    station_dir = Path(layout.landing_dir("trafikverket_train_station")) / f"run={run_id}"
    for i, page in enumerate(trafikverket.fetch_stations(s, api_key)):
        write_ndjson(station_dir, f"p{i:04d}", page)

    log.info("Trafikverket: %d tåglägen", total)
    return total


def ingest_smhi(layout: Layout, since_days: int, parameters: Sequence[int], max_workers: int = 8) -> int:
    """Hämtar observationer för alla aktiva SMHI-stationer, från ``since_days`` dagar bakåt."""
    s = http.session()
    run_id = _run_id()
    since = datetime.now(timezone.utc) - timedelta(days=since_days)
    since_ms = int(since.timestamp() * 1000)
    total = 0

    for parameter in parameters:
        stations = smhi.list_stations(s, parameter)
        write_ndjson(Path(layout.landing_dir("smhi_station")) / f"run={run_id}", f"parameter-{parameter}", stations)

        active = [st["station_id"] for st in stations if st["active"]]
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            results = pool.map(lambda sid: smhi.fetch_observations(s, sid, parameter, since_ms), active)
            rows = [row for station_rows in results for row in station_rows]

        write_ndjson(Path(layout.landing_dir("smhi_observation")) / f"run={run_id}", f"parameter-{parameter}", rows)
        log.info("SMHI parameter %d: %d stationer, %d observationer", parameter, len(active), len(rows))
        total += len(rows)

    return total
