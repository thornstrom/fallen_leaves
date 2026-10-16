"""Klient för SMHI:s öppna meteorologiska observationer (Metobs)."""

from __future__ import annotations

BASE_URL = "https://opendata-download-metobs.smhi.se/api/version/1.0"
TIMEOUT_S = 60

# Parametrar per timme: 1 = lufttemperatur (momentanvärde), 7 = nederbörd (summa 1 timme).
AIR_TEMPERATURE = 1
PRECIPITATION = 7


def list_stations(session, parameter: int) -> list[dict]:
    resp = session.get(f"{BASE_URL}/parameter/{parameter}.json", timeout=TIMEOUT_S)
    resp.raise_for_status()
    return [
        {
            "station_id": str(s.get("key") or s["id"]),
            "name": s.get("name"),
            "latitude": s.get("latitude"),
            "longitude": s.get("longitude"),
            "active": bool(s.get("active")),
            "parameter": parameter,
        }
        for s in resp.json().get("station", [])
    ]


def fetch_observations(session, station_id: str, parameter: int, since_ms: int, period: str = "latest-months") -> list[dict]:
    """Observationer med tidsstämpel (epoch ms, UTC) >= ``since_ms``. Saknad data (404) ger tom lista."""
    url = f"{BASE_URL}/parameter/{parameter}/station/{station_id}/period/{period}/data.json"
    resp = session.get(url, timeout=TIMEOUT_S)
    if resp.status_code == 404:
        return []
    resp.raise_for_status()
    return [
        {
            "station_id": station_id,
            "parameter": parameter,
            "ts_ms": v["date"],
            "value": v.get("value"),
            "quality": v.get("quality"),
        }
        for v in resp.json().get("value") or []
        if v["date"] >= since_ms
    ]
