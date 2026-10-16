"""Landing (rå JSON) → bronze Delta med Auto Loader.

Varje rad i landing-filerna sparas oförändrad som strängen ``payload``. Schemat tolkas först i silver,
så att schemaändringar hos källan aldrig stoppar inläsningen.
"""

from __future__ import annotations

import logging

from pyspark.sql import SparkSession
from pyspark.sql import functions as F

from fallen_leaves.config import BRONZE_SOURCES, Layout

log = logging.getLogger(__name__)


def load_source(spark: SparkSession, layout: Layout, source_table: str) -> None:
    source = source_table.split("_", 1)[0]
    stream = (
        spark.readStream.format("cloudFiles")
        .option("cloudFiles.format", "text")
        .option("pathGlobFilter", "*.json")
        .option("recursiveFileLookup", "true")
        .load(layout.landing_dir(source_table))
        .select(
            F.col("value").alias("payload"),
            F.lit(source).alias("_source"),
            F.col("_metadata.file_path").alias("_source_file"),
            F.current_timestamp().alias("_ingested_at"),
        )
        .withColumn("ingest_date", F.to_date("_ingested_at"))
    )
    query = (
        stream.writeStream.option("checkpointLocation", f"{layout.checkpoint_root}/bronze/{source_table}")
        .partitionBy("ingest_date")
        .trigger(availableNow=True)
        .toTable(layout.table("bronze", source_table))
    )
    query.awaitTermination()
    log.info("Bronze %s: klart", source_table)


def load_all(spark: SparkSession, layout: Layout) -> None:
    for source_table in BRONZE_SOURCES:
        load_source(spark, layout, source_table)
