"""Silver → gold.daily_station_delay_weather och gold.daily_national."""

from __future__ import annotations

from pyspark.sql import Column, DataFrame, Window
from pyspark.sql import functions as F

from fallen_leaves.silver.common import LOCAL_TZ

STATION_TABLE = "daily_station_delay_weather"
NATIONAL_TABLE = "daily_national"

DELAYED_THRESHOLD_MIN = 5
ALL_SWEDEN = "Sverige"


def _safe_div(num: Column, den: Column) -> Column:
    return F.when(den != 0, num / den)


def _local_date(ts: Column) -> Column:
    return F.to_date(F.from_utc_timestamp(ts, LOCAL_TZ))


def daily_weather(weather_hourly: DataFrame) -> DataFrame:
    """Dygnsvärden per väderstation (lokalt datum) och förändring mot föregående dygn."""
    daily = (
        weather_hourly.withColumn("weather_date", _local_date(F.col("ts_hour_utc")))
        .groupBy(F.col("location_id").alias("weather_location_id"), "weather_date")
        .agg(
            F.avg("air_temp_c").alias("temp_mean_c"),
            F.min("air_temp_c").alias("temp_min_c"),
            F.max("air_temp_c").alias("temp_max_c"),
            F.sum("precip_mm").alias("precip_mm"),
            F.count("air_temp_c").alias("temp_hours"),
        )
    )
    w = Window.partitionBy("weather_location_id").orderBy("weather_date")
    prev_date = F.lag("weather_date").over(w)
    prev_mean = F.lag("temp_mean_c").over(w)
    return (
        daily.withColumn(
            "temp_delta_c",
            F.when(F.datediff("weather_date", prev_date) == 1, F.col("temp_mean_c") - prev_mean),
        )
        .withColumn("crossed_zero", (F.col("temp_min_c") < 0) & (F.col("temp_max_c") > 0))
        .withColumn("frost", F.col("temp_min_c") <= 0)
    )


def _daily_delays(events: DataFrame) -> DataFrame:
    arrival = F.col("activity") == "arrival"
    measurable = arrival & ~F.col("is_canceled") & F.col("delay_min").isNotNull()
    delay_pos = F.greatest(F.col("delay_min"), F.lit(0.0))  # tidiga ankomster räknas som 0
    return (
        events.withColumn("event_date", _local_date(F.col("advertised_ts_utc")))
        .groupBy("location_id", "event_date")
        .agg(
            F.countDistinct("train_ident").alias("n_trains"),
            F.count(F.when(measurable, 1)).alias("n_arrivals"),
            F.coalesce(F.sum(F.when(measurable, delay_pos)), F.lit(0.0)).alias("delay_sum_min"),
            F.count(F.when(measurable & (F.col("delay_min") > DELAYED_THRESHOLD_MIN), 1)).alias("n_delayed_5"),
            F.count(F.when(arrival & F.col("is_canceled"), 1)).alias("n_canceled"),
        )
        .withColumn("avg_arrival_delay_min", _safe_div(F.col("delay_sum_min"), F.col("n_arrivals")))
        .withColumn("share_delayed_5", _safe_div(F.col("n_delayed_5"), F.col("n_arrivals")))
    )


def build_daily_station(events: DataFrame, weather_hourly: DataFrame, bridge: DataFrame, rail: DataFrame) -> DataFrame:
    """En rad per tågstation och lokalt datum med förseningsmått och väder från närmaste väderstation."""
    delays = _daily_delays(events)
    weather = daily_weather(weather_hourly).withColumnRenamed("weather_location_id", "_w_location_id")
    stations = rail.select("location_id", F.col("name").alias("station_name"), "region", "country_code", "latitude", "longitude")

    return (
        delays.join(stations, "location_id", "left")
        .join(bridge.withColumnRenamed("distance_km", "weather_distance_km"), "location_id", "left")
        .join(
            weather,
            (F.col("weather_location_id") == F.col("_w_location_id")) & (F.col("event_date") == F.col("weather_date")),
            "left",
        )
        .select(
            "event_date",
            "location_id",
            "station_name",
            "region",
            "country_code",
            "latitude",
            "longitude",
            "n_trains",
            "n_arrivals",
            "delay_sum_min",
            "avg_arrival_delay_min",
            "n_delayed_5",
            "share_delayed_5",
            "n_canceled",
            "weather_location_id",
            "weather_distance_km",
            "temp_mean_c",
            "temp_min_c",
            "temp_max_c",
            "temp_delta_c",
            "precip_mm",
            "crossed_zero",
            "frost",
        )
    )


def _weighted(col: str) -> Column:
    """Medelvärde viktat med antal ankomster (stationer utan värde ingår inte)."""
    has_value = F.col(col).isNotNull()
    return _safe_div(
        F.sum(F.when(has_value, F.col(col) * F.col("n_arrivals"))),
        F.sum(F.when(has_value, F.col("n_arrivals"))),
    )


def _national_aggs() -> list[Column]:
    return [
        F.countDistinct("location_id").alias("n_stations"),
        F.sum("n_trains").alias("n_station_trains"),
        F.sum("n_arrivals").alias("n_arrivals"),
        _safe_div(F.sum("delay_sum_min"), F.sum("n_arrivals")).alias("avg_arrival_delay_min"),
        _safe_div(F.sum("n_delayed_5"), F.sum("n_arrivals")).alias("share_delayed_5"),
        F.sum("n_canceled").alias("n_canceled"),
        _weighted("temp_mean_c").alias("temp_mean_c"),
        _weighted("temp_min_c").alias("temp_min_c"),
        _weighted("temp_delta_c").alias("temp_delta_c"),
        _weighted("precip_mm").alias("precip_mm"),
        _safe_div(F.sum(F.when(F.col("frost"), F.col("n_arrivals"))), F.sum("n_arrivals")).alias("share_arrivals_frost"),
    ]


def build_daily_national(daily_station: DataFrame) -> DataFrame:
    """Dygnsvärden per landsdel och för hela Sverige (bara svenska stationer)."""
    se = daily_station.where(F.col("region").isNotNull() & ~F.col("region").isin("Utland", "Okänd"))
    by_region = se.groupBy("event_date", "region").agg(*_national_aggs())
    total = se.groupBy("event_date").agg(*_national_aggs()).withColumn("region", F.lit(ALL_SWEDEN))
    return by_region.unionByName(total)
