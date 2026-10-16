from datetime import datetime, timezone

from fallen_leaves.silver.weather_obs import transform_observations


def obs(station_id, parameter, iso_utc, value, quality="G"):
    ts = datetime.fromisoformat(iso_utc).replace(tzinfo=timezone.utc)
    return {
        "station_id": station_id,
        "parameter": parameter,
        "ts_ms": int(ts.timestamp() * 1000),
        "value": value,
        "quality": quality,
    }


def test_pivots_temperature_and_precipitation_per_hour(bronze_df):
    df = transform_observations(
        bronze_df(
            [
                obs("98210", 1, "2026-10-15T06:00:00", "3.4"),
                obs("98210", 7, "2026-10-15T06:00:00", "0.2", quality="Y"),
                obs("98210", 1, "2026-10-15T07:00:00", "-0.5"),
            ]
        )
    )

    rows = {r.ts_hour_utc.strftime("%H"): r for r in df.collect()}
    assert rows["06"].location_id == "wx:98210"
    assert rows["06"].air_temp_c == 3.4
    assert rows["06"].precip_mm == 0.2
    assert rows["06"].precip_quality == "Y"
    assert rows["07"].air_temp_c == -0.5
    assert rows["07"].precip_mm is None


def test_latest_ingested_value_wins(spark, bronze_df):
    first = bronze_df([obs("98210", 1, "2026-10-15T06:00:00", "3.4")], ingested_at="2026-10-15 04:00:00")
    corrected = bronze_df([obs("98210", 1, "2026-10-15T06:00:00", "3.1")], ingested_at="2026-10-16 04:00:00")

    rows = transform_observations(first.unionByName(corrected)).collect()

    assert len(rows) == 1
    assert rows[0].air_temp_c == 3.1
