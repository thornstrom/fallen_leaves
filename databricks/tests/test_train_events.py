from fallen_leaves.silver.train_events import transform_announcements


def announcement(**overrides):
    base = {
        "ActivityId": "1500adde-0000-0000-0000-000000000001",
        "ActivityType": "Ankomst",
        "Advertised": True,
        "AdvertisedTimeAtLocation": "2026-10-15T08:10:00.000+02:00",
        "AdvertisedTrainIdent": "541",
        "Canceled": False,
        "Deleted": False,
        "InformationOwner": "SJ",
        "Operator": "SJ",
        "LocationSignature": "Cst",
        "ModifiedTime": "2026-10-15T08:12:00.000+02:00",
        "ScheduledDepartureDateTime": "2026-10-15T00:00:00.000+02:00",
        "TimeAtLocation": "2026-10-15T08:17:00.000+02:00",
        "TimeAtLocationWithSeconds": "2026-10-15T08:17:30.000+02:00",
        "Deviation": [{"Code": "ANA088", "Description": "Banarbete"}],
        "ProductInformation": [{"Code": "PNA014", "Description": "SJ Snabbtåg"}],
        "FromLocation": [{"LocationName": "G", "Priority": 1, "Order": 0}],
        "ToLocation": [{"LocationName": "Cst", "Priority": 1, "Order": 0}],
    }
    base.update(overrides)
    return base


def test_delay_is_computed_in_minutes_with_seconds_precision(bronze_df):
    rows = transform_announcements(bronze_df([announcement()])).collect()

    assert len(rows) == 1
    row = rows[0]
    assert row.delay_min == 7.5
    assert row.activity == "arrival"
    assert row.location_id == "rail:Cst"
    assert str(row.train_date) == "2026-10-15"


def test_timestamps_are_converted_to_utc(bronze_df):
    row = transform_announcements(bronze_df([announcement()])).collect()[0]

    # Sessionens tidszon är UTC i testerna, 08:10+02:00 ska bli 06:10 UTC.
    assert row.advertised_ts_utc.strftime("%H:%M") == "06:10"


def test_falls_back_to_minute_precision_when_seconds_missing(bronze_df):
    rec = announcement(TimeAtLocationWithSeconds=None)
    row = transform_announcements(bronze_df([rec])).collect()[0]

    assert row.delay_min == 7.0


def test_missing_actual_time_gives_null_delay(bronze_df):
    rec = announcement(TimeAtLocation=None, TimeAtLocationWithSeconds=None, Canceled=True)
    row = transform_announcements(bronze_df([rec])).collect()[0]

    assert row.delay_min is None
    assert row.is_canceled is True


def test_keeps_latest_version_per_event(bronze_df):
    old = announcement(ModifiedTime="2026-10-15T08:00:00.000+02:00", TimeAtLocation=None, TimeAtLocationWithSeconds=None)
    new = announcement()
    other_station = announcement(LocationSignature="U", ActivityId="other")

    rows = transform_announcements(bronze_df([old, new, other_station])).collect()

    by_station = {r.location_signature: r for r in rows}
    assert set(by_station) == {"Cst", "U"}
    assert by_station["Cst"].delay_min == 7.5


def test_deleted_flag_is_kept_for_merge(bronze_df):
    rows = transform_announcements(bronze_df([announcement(Deleted=True)])).collect()

    assert rows[0].is_deleted is True


def test_deviation_codes_and_product_are_extracted(bronze_df):
    row = transform_announcements(bronze_df([announcement()])).collect()[0]

    assert row.deviation_codes == ["ANA088"]
    assert row.product == "SJ Snabbtåg"
    assert row.from_location == "G"
    assert row.to_location == "Cst"
