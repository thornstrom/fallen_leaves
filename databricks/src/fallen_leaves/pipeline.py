"""Silver- och gold-stegen som körs av Databricks-jobben."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F

from fallen_leaves import delta_io
from fallen_leaves.config import Layout
from fallen_leaves.gold import correlation, daily_delay_weather
from fallen_leaves.silver import conform_locations, train_events, weather_obs

log = logging.getLogger(__name__)


def _bronze(spark: SparkSession, layout: Layout, name: str, lookback_days: int | None) -> DataFrame:
    df = spark.table(layout.table("bronze", name))
    if lookback_days is not None:
        df = df.where(F.col("ingest_date") >= F.date_sub(F.current_date(), lookback_days))
    return df


def run_silver(spark: SparkSession, layout: Layout, lookback_days: int | None = 7) -> None:
    """Bygger silver från bronze. ``lookback_days=None`` bearbetar hela bronze (backfill)."""
    # Platser: små tabeller, byggs om helt från senaste versionen i bronze.
    rail = conform_locations.rail_locations(_bronze(spark, layout, "trafikverket_train_station", None))
    weather = conform_locations.weather_locations(_bronze(spark, layout, "smhi_station", None))
    rail.cache()
    weather.cache()
    delta_io.overwrite(conform_locations.dim_location(rail, weather), layout.table("silver", conform_locations.DIM_TABLE))
    delta_io.overwrite(conform_locations.source_mapping(rail, weather), layout.table("silver", conform_locations.MAP_TABLE))
    delta_io.overwrite(
        conform_locations.bridge_nearest_weather(rail, weather), layout.table("silver", conform_locations.BRIDGE_TABLE)
    )

    events = train_events.transform_announcements(_bronze(spark, layout, "trafikverket_train_announcement", lookback_days))
    delta_io.merge_upsert(
        spark,
        events,
        layout.table("silver", train_events.TABLE),
        train_events.KEYS,
        update_when="s.modified_ts_utc >= t.modified_ts_utc OR t.modified_ts_utc IS NULL",
        delete_when="s.is_deleted",
        insert_when="NOT s.is_deleted",
    )

    observations = weather_obs.transform_observations(_bronze(spark, layout, "smhi_observation", lookback_days))
    delta_io.merge_upsert(spark, observations, layout.table("silver", weather_obs.TABLE), weather_obs.KEYS)
    log.info("Silver: klart")


def run_gold(spark: SparkSession, layout: Layout, gold_root: str, max_lag: int = 2) -> None:
    """Bygger om gold helt. Tabellerna skrivs som external tables under ``gold_root`` så att Synapse kan läsa dem."""
    # Synapse serverless kan inte läsa Delta-tabeller med deletion vectors.
    spark.conf.set("spark.databricks.delta.properties.defaults.enableDeletionVectors", "false")
    computed_at = F.lit(datetime.now(timezone.utc)).cast("timestamp")

    events = spark.table(layout.table("silver", train_events.TABLE))
    weather_hourly = spark.table(layout.table("silver", weather_obs.TABLE))
    bridge = spark.table(layout.table("silver", conform_locations.BRIDGE_TABLE))
    rail = spark.table(layout.table("silver", conform_locations.DIM_TABLE)).where("location_type = 'rail_station'")

    def write(df: DataFrame, name: str) -> None:
        delta_io.overwrite(df.withColumn("computed_at", computed_at), layout.table("gold", name), f"{gold_root}/{name}")

    station = daily_delay_weather.build_daily_station(events, weather_hourly, bridge, rail)
    write(station, daily_delay_weather.STATION_TABLE)

    national = daily_delay_weather.build_daily_national(spark.table(layout.table("gold", daily_delay_weather.STATION_TABLE)))
    write(national, daily_delay_weather.NATIONAL_TABLE)

    national_pdf = spark.table(layout.table("gold", daily_delay_weather.NATIONAL_TABLE)).toPandas()
    corr = correlation.compute_correlations(national_pdf, max_lag=max_lag)
    corr_schema = (
        "region string, delay_metric string, weather_metric string, lag_days int, n int, pearson_r double, "
        "p_value_pearson double, spearman_rho double, p_value_spearman double, date_from date, date_to date"
    )
    write(spark.createDataFrame(corr, corr_schema), correlation.TABLE)
    log.info("Gold: klart")
