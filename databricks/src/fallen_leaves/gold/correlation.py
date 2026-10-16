"""gold.daily_national → gold.correlation_results.

Liten datamängd (en rad per landsdel och dygn), så beräkningen görs i pandas/scipy.
"""

from __future__ import annotations

import warnings
from datetime import timedelta

import numpy as np
import pandas as pd
from scipy import stats

TABLE = "correlation_results"

DELAY_METRICS = ["avg_arrival_delay_min", "share_delayed_5"]
WEATHER_METRICS = ["temp_mean_c", "temp_min_c", "temp_delta_c"]
MIN_POINTS = 3

COLUMNS = [
    "region",
    "delay_metric",
    "weather_metric",
    "lag_days",
    "n",
    "pearson_r",
    "p_value_pearson",
    "spearman_rho",
    "p_value_spearman",
    "date_from",
    "date_to",
]


def _corr(x: pd.Series, y: pd.Series):
    if len(x) < MIN_POINTS or x.nunique() < 2 or y.nunique() < 2:
        return (np.nan,) * 4
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        pr = stats.pearsonr(x, y)
        sr = stats.spearmanr(x, y)
    return float(pr[0]), float(pr[1]), float(sr[0]), float(sr[1])


def compute_correlations(daily: pd.DataFrame, max_lag: int = 2) -> pd.DataFrame:
    """Korrelation mellan förseningsmått dag d och vädermått dag d - lag, per region och lag."""
    daily = daily.copy()
    daily["event_date"] = pd.to_datetime(daily["event_date"]).dt.date
    rows = []
    for region, g in daily.groupby("region"):
        delays = g[["event_date", *DELAY_METRICS]]
        for lag in range(max_lag + 1):
            weather = g[["event_date", *WEATHER_METRICS]].copy()
            weather["event_date"] = weather["event_date"] + timedelta(days=lag)
            joined = delays.merge(weather, on="event_date", suffixes=("", "_w"))
            for dm in DELAY_METRICS:
                for wm in WEATHER_METRICS:
                    pair = joined[["event_date", dm, wm]].dropna()
                    pearson_r, p_pearson, spearman_rho, p_spearman = _corr(pair[dm], pair[wm])
                    rows.append(
                        {
                            "region": region,
                            "delay_metric": dm,
                            "weather_metric": wm,
                            "lag_days": lag,
                            "n": int(len(pair)),
                            "pearson_r": pearson_r,
                            "p_value_pearson": p_pearson,
                            "spearman_rho": spearman_rho,
                            "p_value_spearman": p_spearman,
                            "date_from": pair["event_date"].min() if len(pair) else None,
                            "date_to": pair["event_date"].max() if len(pair) else None,
                        }
                    )
    return pd.DataFrame(rows, columns=COLUMNS)
