"""Gemensamma hjälpfunktioner och nyckelkonventioner för silver-lagret.

Alla källor kopplas ihop via två nycklar:
  * ``location_id`` – kanonisk plats, ``<typ>:<källnyckel>`` (t.ex. ``rail:Cst``, ``wx:98210``).
    Nya källor mappar sina egna platsnycklar till ett location_id i ``silver.map_source_location``.
  * tid i UTC – ``ts_hour_utc`` för timdata och lokal ``date`` (Europe/Stockholm) för dygnsdata.
"""

from __future__ import annotations

from typing import Sequence

from pyspark.sql import Column, DataFrame, Window
from pyspark.sql import functions as F

LOCAL_TZ = "Europe/Stockholm"

RAIL_PREFIX = "rail"
WEATHER_PREFIX = "wx"


def location_id(prefix: str, key: Column) -> Column:
    return F.concat(F.lit(f"{prefix}:"), key)


def latest_per_key(df: DataFrame, keys: Sequence[str], order_cols: Sequence[Column]) -> DataFrame:
    """Behåller en rad per nyckel, den som sorteras först enligt ``order_cols`` (ange desc för senaste)."""
    w = Window.partitionBy(*keys).orderBy(*order_cols)
    return df.withColumn("_rn", F.row_number().over(w)).where("_rn = 1").drop("_rn")


def to_utc(col: Column) -> Column:
    """ISO 8601-sträng med tidszon (t.ex. 2026-10-15T08:10:00.000+02:00) till timestamp.

    Spark lagrar timestamps som absoluta tidpunkter, så värdet är UTC oberoende av sessionens tidszon.
    """
    return col.cast("timestamp")
