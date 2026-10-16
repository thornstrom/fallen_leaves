"""Trafikverket TrainAnnouncement → silver.fact_train_event."""

from __future__ import annotations

from pyspark.sql import DataFrame
from pyspark.sql import functions as F
from pyspark.sql.types import ArrayType, BooleanType, IntegerType, StringType, StructField, StructType

from fallen_leaves.silver.common import RAIL_PREFIX, latest_per_key, location_id, to_utc

TABLE = "fact_train_event"
KEYS = ["train_ident", "train_date", "location_signature", "activity"]

_CODE_DESC = ArrayType(StructType([StructField("Code", StringType()), StructField("Description", StringType())]))
_LOCATIONS = ArrayType(
    StructType(
        [
            StructField("LocationName", StringType()),
            StructField("Priority", IntegerType()),
            StructField("Order", IntegerType()),
        ]
    )
)

ANNOUNCEMENT_SCHEMA = StructType(
    [
        StructField("ActivityId", StringType()),
        StructField("ActivityType", StringType()),
        StructField("Advertised", BooleanType()),
        StructField("AdvertisedTimeAtLocation", StringType()),
        StructField("AdvertisedTrainIdent", StringType()),
        StructField("Canceled", BooleanType()),
        StructField("Deleted", BooleanType()),
        StructField("Deviation", _CODE_DESC),
        StructField("EstimatedTimeAtLocation", StringType()),
        StructField("InformationOwner", StringType()),
        StructField("Operator", StringType()),
        StructField("LocationSignature", StringType()),
        StructField("ModifiedTime", StringType()),
        StructField("ScheduledDepartureDateTime", StringType()),
        StructField("TimeAtLocation", StringType()),
        StructField("TimeAtLocationWithSeconds", StringType()),
        StructField("TrackAtLocation", StringType()),
        StructField("ProductInformation", _CODE_DESC),
        StructField("FromLocation", _LOCATIONS),
        StructField("ToLocation", _LOCATIONS),
    ]
)

_ACTIVITY = {"Ankomst": "arrival", "Avgang": "departure"}


def transform_announcements(bronze: DataFrame) -> DataFrame:
    """Parsar bronze-payload och returnerar en rad per tåg, dag, station och aktivitet (senaste versionen).

    Raderade händelser behålls med ``is_deleted = true`` så att MERGE kan ta bort dem.
    """
    a = F.from_json("payload", ANNOUNCEMENT_SCHEMA).alias("a")
    parsed = bronze.select(a, "_ingested_at").select("a.*", "_ingested_at")

    activity = F.coalesce(
        *[F.when(F.col("ActivityType") == k, F.lit(v)) for k, v in _ACTIVITY.items()], F.lower("ActivityType")
    )
    advertised = to_utc(F.col("AdvertisedTimeAtLocation"))
    actual = to_utc(F.coalesce("TimeAtLocationWithSeconds", "TimeAtLocation"))

    events = parsed.select(
        F.col("AdvertisedTrainIdent").alias("train_ident"),
        F.to_date(F.substring("ScheduledDepartureDateTime", 1, 10)).alias("train_date"),
        F.col("LocationSignature").alias("location_signature"),
        location_id(RAIL_PREFIX, F.col("LocationSignature")).alias("location_id"),
        activity.alias("activity"),
        F.col("ActivityId").alias("activity_id"),
        advertised.alias("advertised_ts_utc"),
        to_utc(F.col("EstimatedTimeAtLocation")).alias("estimated_ts_utc"),
        actual.alias("actual_ts_utc"),
        ((F.unix_timestamp(actual) - F.unix_timestamp(advertised)) / 60.0).alias("delay_min"),
        F.coalesce("Canceled", F.lit(False)).alias("is_canceled"),
        F.coalesce("Deleted", F.lit(False)).alias("is_deleted"),
        F.coalesce("Advertised", F.lit(False)).alias("is_advertised"),
        F.col("Deviation.Code").alias("deviation_codes"),
        F.col("Deviation.Description").alias("deviation_texts"),
        F.col("ProductInformation")[0]["Description"].alias("product"),
        F.col("FromLocation")[0]["LocationName"].alias("from_location"),
        F.col("ToLocation")[0]["LocationName"].alias("to_location"),
        F.col("TrackAtLocation").alias("track"),
        F.col("Operator").alias("operator"),
        to_utc(F.col("ModifiedTime")).alias("modified_ts_utc"),
        F.lit("trafikverket").alias("source"),
        F.col("_ingested_at"),
    ).where(F.col("train_ident").isNotNull() & F.col("location_signature").isNotNull())

    return latest_per_key(events, KEYS, [F.col("modified_ts_utc").desc_nulls_last(), F.col("_ingested_at").desc()])
