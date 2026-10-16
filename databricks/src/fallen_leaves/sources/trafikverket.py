"""Klient för Trafikverkets öppna API (api.trafikinfo.trafikverket.se)."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Iterator, Sequence
from xml.sax.saxutils import quoteattr

API_URL = "https://api.trafikinfo.trafikverket.se/v2/data.json"
ANNOUNCEMENT_SCHEMA_VERSION = "1.9"
STATION_SCHEMA_VERSION = "1.5"
DEFAULT_PAGE_SIZE = 5000
TIMEOUT_S = 120


class TrafikverketError(RuntimeError):
    pass


def _attr(value: object) -> str:
    # quoteattr lägger till citattecken och escapar &, <, > och ".
    return quoteattr(str(value), {'"': "&quot;"})


def _request(api_key: str, query: str) -> str:
    return f"<REQUEST><LOGIN authenticationkey={_attr(api_key)} />{query}</REQUEST>"


def announcement_query(api_key: str, day: date, operators: Sequence[str], limit: int, skip: int) -> str:
    """Alla TrainAnnouncement för tåg med avgångsdag ``day`` som körs av någon av ``operators``."""
    start = day.isoformat() + "T00:00:00"
    end = (day + timedelta(days=1)).isoformat() + "T00:00:00"
    operator_filters = "".join(
        f'<EQ name="Operator" value={_attr(op)} /><EQ name="InformationOwner" value={_attr(op)} />' for op in operators
    )
    query = (
        f'<QUERY objecttype="TrainAnnouncement" schemaversion="{ANNOUNCEMENT_SCHEMA_VERSION}" '
        f'orderby="ActivityId" limit="{limit}" skip="{skip}">'
        "<FILTER><AND>"
        f'<GTE name="ScheduledDepartureDateTime" value="{start}" />'
        f'<LT name="ScheduledDepartureDateTime" value="{end}" />'
        f"<OR>{operator_filters}</OR>"
        "</AND></FILTER>"
        "</QUERY>"
    )
    return _request(api_key, query)


def station_query(api_key: str, limit: int, skip: int) -> str:
    query = (
        f'<QUERY objecttype="TrainStation" schemaversion="{STATION_SCHEMA_VERSION}" '
        f'orderby="LocationSignature" limit="{limit}" skip="{skip}" />'
    )
    return _request(api_key, query)


def _post(session, xml: str, objecttype: str) -> list[dict]:
    resp = session.post(API_URL, data=xml.encode("utf-8"), headers={"Content-Type": "text/xml"}, timeout=TIMEOUT_S)
    body = resp.json()
    results = body.get("RESPONSE", {}).get("RESULT", [])
    if not results:
        resp.raise_for_status()
        raise TrafikverketError(f"Oväntat svar från Trafikverket: {body}")
    result = results[0]
    if "ERROR" in result:
        err = result["ERROR"]
        raise TrafikverketError(f"{err.get('SOURCE')}: {err.get('MESSAGE')}")
    resp.raise_for_status()
    return result.get(objecttype, [])


def _paginate(session, build_query, objecttype: str, page_size: int) -> Iterator[list[dict]]:
    skip = 0
    while True:
        page = _post(session, build_query(page_size, skip), objecttype)
        if page:
            yield page
        if len(page) < page_size:
            return
        skip += page_size


def fetch_announcements(
    session, api_key: str, day: date, operators: Sequence[str], page_size: int = DEFAULT_PAGE_SIZE
) -> Iterator[list[dict]]:
    """Ger en lista med poster per sida."""
    return _paginate(
        session,
        lambda limit, skip: announcement_query(api_key, day, operators, limit, skip),
        "TrainAnnouncement",
        page_size,
    )


def fetch_stations(session, api_key: str, page_size: int = DEFAULT_PAGE_SIZE) -> Iterator[list[dict]]:
    return _paginate(session, lambda limit, skip: station_query(api_key, limit, skip), "TrainStation", page_size)
