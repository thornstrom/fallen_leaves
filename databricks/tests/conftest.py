import json
import os
import time

import pytest
from pyspark.sql import SparkSession

# pyspark konverterar timestamps via Pythons lokala tidszon; kör allt i UTC så att testerna
# blir oberoende av maskinens inställning.
os.environ["TZ"] = "UTC"
time.tzset()


@pytest.fixture(scope="session")
def spark():
    session = (
        SparkSession.builder.master("local[1]")
        .appName("fallen_leaves_tests")
        .config("spark.sql.session.timeZone", "UTC")
        .config("spark.sql.shuffle.partitions", "1")
        .config("spark.ui.enabled", "false")
        .getOrCreate()
    )
    yield session
    session.stop()


@pytest.fixture
def bronze_df(spark):
    """Bygger en bronze-DataFrame (payload som JSON-sträng) från en lista med dictar."""

    def _build(records, ingested_at="2026-10-16 04:00:00"):
        rows = [(json.dumps(r), ingested_at) for r in records]
        return spark.createDataFrame(rows, "payload string, _ingested_at string").selectExpr(
            "payload", "cast(_ingested_at as timestamp) as _ingested_at"
        )

    return _build
