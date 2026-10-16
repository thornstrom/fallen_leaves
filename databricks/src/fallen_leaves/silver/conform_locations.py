"""Platser från alla källor → silver.dim_location, silver.map_source_location och silver.bridge_location_weather."""

from __future__ import annotations

from pyspark.sql import Column, DataFrame
from pyspark.sql import functions as F
from pyspark.sql.types import (
    ArrayType,
    BooleanType,
    DoubleType,
    IntegerType,
    StringType,
    StructField,
    StructType,
)

from fallen_leaves.silver.common import RAIL_PREFIX, WEATHER_PREFIX, latest_per_key, location_id, to_utc

DIM_TABLE = "dim_location"
MAP_TABLE = "map_source_location"
BRIDGE_TABLE = "bridge_location_weather"

DEFAULT_MAX_KM = 50.0
EARTH_RADIUS_KM = 6371.0

STATION_SCHEMA = StructType(
    [
        StructField("LocationSignature", StringType()),
        StructField("AdvertisedLocationName", StringType()),
        StructField("Geometry", StructType([StructField("WGS84", StringType())])),
        StructField("CountryCode", StringType()),
        StructField("CountyNo", ArrayType(IntegerType())),
        StructField("Advertised", BooleanType()),
        StructField("Deleted", BooleanType()),
        StructField("ModifiedTime", StringType()),
    ]
)

SMHI_STATION_SCHEMA = StructType(
    [
        StructField("station_id", StringType()),
        StructField("name", StringType()),
        StructField("latitude", DoubleType()),
        StructField("longitude", DoubleType()),
        StructField("active", BooleanType()),
        StructField("parameter", IntegerType()),
    ]
)

# Länsnummer (SCB) → landsdel.
_SVEALAND = {1, 3, 4, 17, 18, 19, 20}
_GOTALAND = {5, 6, 7, 8, 9, 10, 12, 13, 14}
_NORRLAND = {21, 22, 23, 24, 25}

DIM_COLUMNS = [
    "location_id",
    "location_type",
    "name",
    "latitude",
    "longitude",
    "country_code",
    "region",
    "source",
    "source_key",
]


def region_for_county(county: int | None, latitude: float | None, country_code: str | None) -> str:
    """Landsdel utifrån länsnummer, med latitud som reserv när län saknas."""
    if country_code and country_code != "SE":
        return "Utland"
    if county in _SVEALAND:
        return "Svealand"
    if county in _GOTALAND:
        return "Götaland"
    if county in _NORRLAND:
        return "Norrland"
    if latitude is None:
        return "Okänd"
    if latitude >= 60.6:
        return "Norrland"
    if latitude >= 58.8:
        return "Svealand"
    return "Götaland"


def _region_expr(county: Column, lat: Column, country: Column) -> Column:
    """Spark-version av region_for_county (samma regler)."""

    def in_set(s):
        return county.isin(*sorted(s))

    return (
        F.when(country.isNotNull() & (country != "SE"), "Utland")
        .when(in_set(_SVEALAND), "Svealand")
        .when(in_set(_GOTALAND), "Götaland")
        .when(in_set(_NORRLAND), "Norrland")
        .when(lat.isNull(), "Okänd")
        .when(lat >= 60.6, "Norrland")
        .when(lat >= 58.8, "Svealand")
        .otherwise("Götaland")
    )


def rail_locations(bronze_stations: DataFrame) -> DataFrame:
    """Trafikverkets driftplatser som kanoniska platser (senaste versionen, utan raderade)."""
    s = F.from_json("payload", STATION_SCHEMA).alias("s")
    parsed = bronze_stations.select(s, "_ingested_at").select("s.*", "_ingested_at")
    latest = latest_per_key(
        parsed,
        ["LocationSignature"],
        [to_utc(F.col("ModifiedTime")).desc_nulls_last(), F.col("_ingested_at").desc()],
    ).where(~F.coalesce("Deleted", F.lit(False)))

    point = F.regexp_extract("Geometry.WGS84", r"POINT \(([-\d.]+) ([-\d.]+)\)", 0)
    lon = F.regexp_extract("Geometry.WGS84", r"POINT \(([-\d.]+) ([-\d.]+)\)", 1).cast("double")
    lat = F.regexp_extract("Geometry.WGS84", r"POINT \(([-\d.]+) ([-\d.]+)\)", 2).cast("double")
    with_coords = latest.withColumn("_lon", F.when(point != "", lon)).withColumn("_lat", F.when(point != "", lat))

    return with_coords.select(
        location_id(RAIL_PREFIX, F.col("LocationSignature")).alias("location_id"),
        F.lit("rail_station").alias("location_type"),
        F.col("AdvertisedLocationName").alias("name"),
        F.col("_lat").alias("latitude"),
        F.col("_lon").alias("longitude"),
        F.col("CountryCode").alias("country_code"),
        _region_expr(F.col("CountyNo")[0], F.col("_lat"), F.col("CountryCode")).alias("region"),
        F.lit("trafikverket").alias("source"),
        F.col("LocationSignature").alias("source_key"),
    )


def weather_locations(bronze_smhi_stations: DataFrame) -> DataFrame:
    """Aktiva SMHI-stationer som mäter lufttemperatur."""
    s = F.from_json("payload", SMHI_STATION_SCHEMA).alias("s")
    parsed = bronze_smhi_stations.select(s, "_ingested_at").select("s.*", "_ingested_at")
    latest = latest_per_key(parsed, ["station_id", "parameter"], [F.col("_ingested_at").desc()])
    temp_stations = latest.where((F.col("parameter") == 1) & F.col("active"))

    return temp_stations.select(
        location_id(WEATHER_PREFIX, F.col("station_id")).alias("location_id"),
        F.lit("weather_station").alias("location_type"),
        "name",
        "latitude",
        "longitude",
        F.lit("SE").alias("country_code"),
        F.lit(None).cast("string").alias("region"),
        F.lit("smhi").alias("source"),
        F.col("station_id").alias("source_key"),
    )


def haversine_km(lat1: Column, lon1: Column, lat2: Column, lon2: Column) -> Column:
    dlat = F.radians(lat2 - lat1)
    dlon = F.radians(lon2 - lon1)
    a = F.sin(dlat / 2) ** 2 + F.cos(F.radians(lat1)) * F.cos(F.radians(lat2)) * F.sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_KM * F.asin(F.sqrt(a))


def bridge_nearest_weather(rail: DataFrame, weather: DataFrame, max_km: float = DEFAULT_MAX_KM) -> DataFrame:
    """Kopplar varje tågstation till närmaste väderstation inom ``max_km``."""
    r = rail.where(F.col("latitude").isNotNull()).select(
        F.col("location_id"), F.col("latitude").alias("r_lat"), F.col("longitude").alias("r_lon")
    )
    w = weather.select(
        F.col("location_id").alias("weather_location_id"),
        F.col("latitude").alias("w_lat"),
        F.col("longitude").alias("w_lon"),
    )
    pairs = r.crossJoin(F.broadcast(w)).withColumn(
        "distance_km", haversine_km(F.col("r_lat"), F.col("r_lon"), F.col("w_lat"), F.col("w_lon"))
    )
    nearest = latest_per_key(pairs.where(F.col("distance_km") <= max_km), ["location_id"], [F.col("distance_km").asc()])
    return nearest.select("location_id", "weather_location_id", "distance_km")


def source_mapping(*dims: DataFrame) -> DataFrame:
    """(source, source_key) → location_id för alla källor."""
    out = None
    for d in dims:
        part = d.select("source", "source_key", "location_id")
        out = part if out is None else out.unionByName(part)
    return out


def dim_location(*dims: DataFrame) -> DataFrame:
    out = None
    for d in dims:
        part = d.select(*DIM_COLUMNS)
        out = part if out is None else out.unionByName(part)
    return out
