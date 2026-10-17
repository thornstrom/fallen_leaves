import json
from datetime import date

import pytest

from fallen_leaves.sources import smhi, trafikverket
from fallen_leaves.sources.landing import write_ndjson


class FakeResponse:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def post(self, url, data=None, headers=None, timeout=None):
        self.calls.append(("POST", url, data))
        return self.responses.pop(0)

    def get(self, url, timeout=None):
        self.calls.append(("GET", url, None))
        return self.responses.pop(0)


def tv_result(objecttype, items):
    return FakeResponse({"RESPONSE": {"RESULT": [{objecttype: items}]}})


def test_announcement_query_filters_operator_and_date():
    xml = trafikverket.announcement_query("KEY", date(2026, 10, 15), ["SJ"], limit=100, skip=200)

    assert 'authenticationkey="KEY"' in xml
    assert 'objecttype="TrainAnnouncement"' in xml
    assert 'limit="100"' in xml and 'skip="200"' in xml
    assert '<EQ name="Operator" value="SJ" />' in xml
    assert '<EQ name="InformationOwner" value="SJ" />' in xml
    assert '<GTE name="ScheduledDepartureDateTime" value="2026-10-15T00:00:00" />' in xml
    assert '<LT name="ScheduledDepartureDateTime" value="2026-10-16T00:00:00" />' in xml


def test_station_query_uses_rail_infrastructure_namespace():
    # Utan namespace svarar API:t "ObjectType 'TrainStation' does not exists".
    xml = trafikverket.station_query("KEY", limit=100, skip=0)

    assert 'objecttype="TrainStation"' in xml
    assert 'namespace="rail.infrastructure"' in xml


def test_query_escapes_values():
    xml = trafikverket.announcement_query('K"<', date(2026, 10, 15), ["A&B"], limit=1, skip=0)

    assert "A&amp;B" in xml
    assert "K&quot;&lt;" in xml


def test_fetch_paginates_until_short_page():
    session = FakeSession([tv_result("TrainAnnouncement", [{"a": 1}, {"a": 2}]), tv_result("TrainAnnouncement", [{"a": 3}])])

    pages = list(trafikverket.fetch_announcements(session, "KEY", date(2026, 10, 15), ["SJ"], page_size=2))

    assert pages == [[{"a": 1}, {"a": 2}], [{"a": 3}]]
    assert 'skip="2"' in session.calls[1][2].decode("utf-8")


def test_fetch_raises_on_api_error():
    session = FakeSession([FakeResponse({"RESPONSE": {"RESULT": [{"ERROR": {"SOURCE": "Auth", "MESSAGE": "Invalid key"}}]}})])

    with pytest.raises(trafikverket.TrafikverketError, match="Invalid key"):
        list(trafikverket.fetch_announcements(session, "KEY", date(2026, 10, 15), ["SJ"]))


def test_smhi_stations_are_normalised():
    session = FakeSession(
        [FakeResponse({"station": [{"key": "98210", "name": "Stockholm", "latitude": 59.34, "longitude": 18.05, "active": True}]})]
    )

    stations = smhi.list_stations(session, parameter=1)

    assert stations == [
        {"station_id": "98210", "name": "Stockholm", "latitude": 59.34, "longitude": 18.05, "active": True, "parameter": 1}
    ]


def test_smhi_observations_filtered_by_since():
    session = FakeSession(
        [
            FakeResponse(
                {
                    "value": [
                        {"date": 1000, "value": "1.0", "quality": "G"},
                        {"date": 5000, "value": "2.0", "quality": "Y"},
                    ]
                }
            )
        ]
    )

    rows = smhi.fetch_observations(session, "98210", parameter=1, since_ms=2000)

    assert rows == [{"station_id": "98210", "parameter": 1, "ts_ms": 5000, "value": "2.0", "quality": "Y"}]
    assert session.calls[0][1].endswith("/parameter/1/station/98210/period/latest-months/data.json")


def test_smhi_missing_station_data_returns_empty():
    session = FakeSession([FakeResponse({}, status=404)])

    assert smhi.fetch_observations(session, "1", parameter=1, since_ms=0) == []


def test_write_ndjson(tmp_path):
    path = write_ndjson(tmp_path / "a" / "b", "part-0", [{"x": 1}, {"x": "å"}])

    lines = path.read_text(encoding="utf-8").splitlines()
    assert [json.loads(line) for line in lines] == [{"x": 1}, {"x": "å"}]
    assert path.name == "part-0.json"


def test_write_ndjson_skips_empty(tmp_path):
    assert write_ndjson(tmp_path, "part-0", []) is None
    assert list(tmp_path.iterdir()) == []
