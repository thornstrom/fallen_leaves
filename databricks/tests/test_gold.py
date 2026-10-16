from datetime import date, datetime

import numpy as np
import pandas as pd
import pytest

from fallen_leaves.gold.correlation import compute_correlations
from fallen_leaves.gold.daily_delay_weather import build_daily_national, build_daily_station

EVENT_SCHEMA = (
    "train_ident string, location_id string, activity string, advertised_ts_utc timestamp, "
    "delay_min double, is_canceled boolean"
)
WEATHER_SCHEMA = "location_id string, ts_hour_utc timestamp, air_temp_c double, precip_mm double"
BRIDGE_SCHEMA = "location_id string, weather_location_id string, distance_km double"
RAIL_SCHEMA = "location_id string, name string, region string, country_code string, latitude double, longitude double"


@pytest.fixture
def rail(spark):
    return spark.createDataFrame(
        [("rail:Cst", "Stockholm C", "Svealand", "SE", 59.33, 18.06), ("rail:G", "Göteborg C", "Götaland", "SE", 57.71, 11.97)],
        RAIL_SCHEMA,
    )


@pytest.fixture
def bridge(spark):
    return spark.createDataFrame([("rail:Cst", "wx:1", 1.5), ("rail:G", "wx:2", 3.0)], BRIDGE_SCHEMA)


def ts(s):
    return datetime.fromisoformat(s)


def test_daily_station_aggregates_delays_and_weather(spark, rail, bridge):
    events = spark.createDataFrame(
        [
            ("1", "rail:Cst", "arrival", ts("2026-10-15T06:00:00"), 10.0, False),
            ("2", "rail:Cst", "arrival", ts("2026-10-15T07:00:00"), -2.0, False),  # tidigt räknas som 0
            ("3", "rail:Cst", "arrival", ts("2026-10-15T08:00:00"), None, True),
            ("1", "rail:Cst", "departure", ts("2026-10-15T06:05:00"), 12.0, False),  # avgångar ingår inte i förseningsmått
            # 23:30 UTC den 14:e är 01:30 lokal tid den 15:e
            ("4", "rail:Cst", "arrival", ts("2026-10-14T23:30:00"), 6.0, False),
        ],
        EVENT_SCHEMA,
    )
    weather = spark.createDataFrame(
        [
            ("wx:1", ts("2026-10-14T10:00:00"), 6.0, 0.0),
            ("wx:1", ts("2026-10-15T02:00:00"), -1.0, 0.0),
            ("wx:1", ts("2026-10-15T12:00:00"), 3.0, 1.5),
        ],
        WEATHER_SCHEMA,
    )

    rows = {(r.location_id, r.event_date): r for r in build_daily_station(events, weather, bridge, rail).collect()}
    r = rows[("rail:Cst", date(2026, 10, 15))]

    assert r.n_trains == 4
    assert r.n_arrivals == 3
    assert r.avg_arrival_delay_min == pytest.approx((10 + 0 + 6) / 3)
    assert r.n_delayed_5 == 2
    assert r.share_delayed_5 == pytest.approx(2 / 3)
    assert r.n_canceled == 1
    assert r.temp_mean_c == pytest.approx(1.0)
    assert r.temp_min_c == -1.0
    assert r.temp_max_c == 3.0
    assert r.precip_mm == 1.5
    assert r.temp_delta_c == pytest.approx(1.0 - 6.0)
    assert r.crossed_zero is True
    assert r.frost is True
    assert r.region == "Svealand"
    assert r.weather_distance_km == 1.5


def test_daily_national_weights_by_arrivals(spark, rail, bridge):
    events = spark.createDataFrame(
        [
            ("1", "rail:Cst", "arrival", ts("2026-10-15T06:00:00"), 10.0, False),
            ("2", "rail:G", "arrival", ts("2026-10-15T06:00:00"), 0.0, False),
            ("3", "rail:G", "arrival", ts("2026-10-15T07:00:00"), 0.0, False),
        ],
        EVENT_SCHEMA,
    )
    weather = spark.createDataFrame(
        [("wx:1", ts("2026-10-15T10:00:00"), 0.0, 0.0), ("wx:2", ts("2026-10-15T10:00:00"), 6.0, 0.0)],
        WEATHER_SCHEMA,
    )

    daily = build_daily_station(events, weather, bridge, rail)
    rows = {r.region: r for r in build_daily_national(daily).collect()}

    assert set(rows) == {"Sverige", "Svealand", "Götaland"}
    assert rows["Sverige"].n_arrivals == 3
    assert rows["Sverige"].avg_arrival_delay_min == pytest.approx(10 / 3)
    assert rows["Sverige"].temp_mean_c == pytest.approx((0 * 1 + 6 * 2) / 3)


def test_correlation_detects_lagged_relationship():
    rng = np.random.default_rng(42)
    days = pd.date_range("2026-09-01", periods=60, freq="D")
    temp = 10 - np.arange(60) * 0.2 + rng.normal(0, 1, 60)
    # Förseningen beror på gårdagens temperatur (lag 1).
    delay = np.r_[np.nan, 5 - 0.8 * temp[:-1]] + rng.normal(0, 0.1, 60)
    pdf = pd.DataFrame(
        {
            "event_date": days.date,
            "region": "Sverige",
            "avg_arrival_delay_min": delay,
            "share_delayed_5": delay / 10,
            "temp_mean_c": temp,
            "temp_min_c": temp - 3,
            "temp_delta_c": np.r_[np.nan, np.diff(temp)],
            "n_arrivals": 100,
        }
    )

    res = compute_correlations(pdf, max_lag=2)
    sel = res[(res.delay_metric == "avg_arrival_delay_min") & (res.weather_metric == "temp_mean_c")].set_index("lag_days")

    assert sel.loc[1, "pearson_r"] < -0.95
    assert sel.loc[1, "p_value_pearson"] < 0.001
    assert sel.loc[1, "n"] == 59
    assert {"spearman_rho", "p_value_spearman", "region"} <= set(res.columns)


def test_correlation_returns_nan_when_too_few_points():
    pdf = pd.DataFrame(
        {
            "event_date": pd.date_range("2026-10-01", periods=2, freq="D").date,
            "region": "Norrland",
            "avg_arrival_delay_min": [1.0, 2.0],
            "share_delayed_5": [0.1, 0.2],
            "temp_mean_c": [1.0, 0.0],
            "temp_min_c": [0.0, -1.0],
            "temp_delta_c": [np.nan, -1.0],
            "n_arrivals": [10, 10],
        }
    )

    res = compute_correlations(pdf, max_lag=0)

    assert res["pearson_r"].isna().all()
