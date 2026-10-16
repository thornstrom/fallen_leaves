"""Skrivning till Delta-tabeller i Unity Catalog."""

from __future__ import annotations

from typing import Sequence

from pyspark.sql import DataFrame, SparkSession


def merge_upsert(
    spark: SparkSession,
    df: DataFrame,
    table: str,
    keys: Sequence[str],
    *,
    update_when: str | None = None,
    delete_when: str | None = None,
    insert_when: str | None = None,
) -> None:
    """MERGE på ``keys``. Villkoren skrivs i SQL med aliasen ``t`` (mål) och ``s`` (källa)."""
    if not spark.catalog.tableExists(table):
        initial = df.alias("s").where(insert_when) if insert_when else df
        initial.write.format("delta").saveAsTable(table)
        return

    from delta.tables import DeltaTable

    on = " AND ".join(f"t.{k} <=> s.{k}" for k in keys)
    merge = DeltaTable.forName(spark, table).alias("t").merge(df.alias("s"), on)
    if delete_when:
        merge = merge.whenMatchedDelete(condition=delete_when)
    merge = merge.whenMatchedUpdateAll(condition=update_when)
    merge = merge.whenNotMatchedInsertAll(condition=insert_when)
    merge.execute()


def overwrite(df: DataFrame, table: str, path: str | None = None) -> None:
    """Skriver om hela tabellen. Med ``path`` blir det en external table på den sökvägen."""
    writer = df.write.format("delta").mode("overwrite").option("overwriteSchema", "true")
    if path:
        writer = writer.option("path", path)
    writer.saveAsTable(table)
