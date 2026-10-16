import pytest

from fallen_leaves.silver.conform_locations import (
    bridge_nearest_weather,
    rail_locations,
    region_for_county,
    weather_locations,
)


def station(sig, name, lon, lat, county=(1,), country="SE", deleted=False, modified="2026-10-01T00:00:00.000+02:00"):
    return {
        "LocationSignature": sig,
        "AdvertisedLocationName": name,
        "Geometry": {"WGS84": f"POINT ({lon} {lat})"},
        "CountryCode": country,
        "CountyNo": list(county),
        "Advertised": True,
        "Deleted": deleted,
        "ModifiedTime": modified,
    }


def smhi(station_id, name, lat, lon, active=True):
    return {
        "station_id": station_id,
        "name": name,
        "latitude": lat,
        "longitude": lon,
        "active": active,
        "parameter": 1,
    }


@pytest.mark.parametrize(
    "county,lat,expected",
    [
        (1, 59.3, "Svealand"),
        (14, 57.7, "Götaland"),
        (25, 65.6, "Norrland"),
        (None, 63.0, "Norrland"),
        (None, 56.0, "Götaland"),
    ],
)
def test_region_for_county(county, lat, expected):
    assert region_for_county(county, lat, "SE") == expected


def test_region_outside_sweden():
    assert region_for_county(None, 59.9, "NO") == "Utland"


def test_rail_locations_parse_wgs84_and_assign_region(bronze_df):
    df = rail_locations(bronze_df([station("Cst", "Stockholm C", 18.0582, 59.3307, county=(1,))]))
    row = df.collect()[0]

    assert row.location_id == "rail:Cst"
    assert row.name == "Stockholm C"
    assert row.latitude == pytest.approx(59.3307)
    assert row.longitude == pytest.approx(18.0582)
    assert row.region == "Svealand"
    assert row.location_type == "rail_station"


def test_rail_locations_drop_deleted_and_keep_latest(bronze_df):
    df = rail_locations(
        bronze_df(
            [
                station("Cst", "Gammalt namn", 18.0, 59.3, modified="2026-01-01T00:00:00.000+01:00"),
                station("Cst", "Stockholm C", 18.0, 59.3, modified="2026-10-01T00:00:00.000+02:00"),
                station("X", "Borttagen", 18.0, 59.3, deleted=True),
            ]
        )
    )

    rows = df.collect()
    assert [r.name for r in rows] == ["Stockholm C"]


def test_weather_locations_only_active(bronze_df):
    df = weather_locations(bronze_df([smhi("98210", "Stockholm", 59.34, 18.05), smhi("1", "Nedlagd", 59.0, 18.0, active=False)]))

    rows = df.collect()
    assert [r.location_id for r in rows] == ["wx:98210"]


def test_bridge_picks_nearest_station_within_limit(bronze_df):
    rail = rail_locations(
        bronze_df(
            [
                station("Cst", "Stockholm C", 18.0582, 59.3307),
                station("Ki", "Kiruna", 20.2253, 67.8558, county=(25,)),
            ]
        )
    )
    wx = weather_locations(
        bronze_df(
            [
                smhi("98210", "Stockholm", 59.3434, 18.0490),  # ~1,5 km från Cst
                smhi("97400", "Arlanda", 59.6269, 17.9545),  # ~33 km från Cst
            ]
        )
    )

    rows = {r.location_id: r for r in bridge_nearest_weather(rail, wx, max_km=50).collect()}

    assert set(rows) == {"rail:Cst"}  # Kiruna har ingen station inom 50 km
    assert rows["rail:Cst"].weather_location_id == "wx:98210"
    assert rows["rail:Cst"].distance_km == pytest.approx(1.5, abs=0.3)
