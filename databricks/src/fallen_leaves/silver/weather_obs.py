"""SMHI-observationer → silver.fact_weather_hourly."""

from __future__ import annotations

from pyspark.sql import DataFrame
from pyspark.sql import functions as F
from pyspark.sql.types import IntegerType, LongType, StringType, StructField, StructType

from fallen_leaves.silver.common import WEATHER_PREFIX, latest_per_key, location_id
from fallen_leaves.sources.smhi import AIR_TEMPERATURE, PRECIPITATION

TABLE = "fact_weather_hourly"
KEYS = ["location_id", "ts_hour_utc"]

OBSERVATION_SCHEMA = StructType(
    [
        StructField("station_id", StringType()),
        StructField("parameter", IntegerType()),
        StructField("ts_ms", LongType()),
        StructField("value", StringType()),
        StructField("quality", StringType()),
    ]
)


def transform_observations(bronze: DataFrame) -> DataFrame:
    """En rad per väderstation och timme med temperatur och nederbörd. Senast inlästa värde vinner."""
    o = F.from_json("payload", OBSERVATION_SCHEMA).alias("o")
    obs = (
        bronze.select(o, "_ingested_at")
        .select("o.*", "_ingested_at")
        .select(
            location_id(WEATHER_PREFIX, F.col("station_id")).alias("location_id"),
            F.date_trunc("hour", F.timestamp_millis("ts_ms")).alias("ts_hour_utc"),
            "parameter",
            F.col("value").cast("double").alias("value"),
            "quality",
            "_ingested_at",
        )
        .where(F.col("parameter").isin(AIR_TEMPERATURE, PRECIPITATION))
    )
    obs = latest_per_key(obs, ["location_id", "ts_hour_utc", "parameter"], [F.col("_ingested_at").desc()])

    def pick(parameter: int, col: str):
        return F.max(F.when(F.col("parameter") == parameter, F.col(col)))

    return obs.groupBy(*KEYS).agg(
        pick(AIR_TEMPERATURE, "value").alias("air_temp_c"),
        pick(AIR_TEMPERATURE, "quality").alias("temp_quality"),
        pick(PRECIPITATION, "value").alias("precip_mm"),
        pick(PRECIPITATION, "quality").alias("precip_quality"),
        F.lit("smhi").alias("source"),
    )
