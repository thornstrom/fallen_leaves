"""Sökvägar och tabellnamn per miljö (catalog)."""

from __future__ import annotations

from dataclasses import dataclass

# Bronze-tabell → katalog i landing-volymen. En ny källa läggs till här och i sources/.
BRONZE_SOURCES = {
    "trafikverket_train_announcement": "trafikverket/train_announcement",
    "trafikverket_train_station": "trafikverket/train_station",
    "smhi_observation": "smhi/observation",
    "smhi_station": "smhi/station",
}


@dataclass(frozen=True)
class Layout:
    catalog: str

    @property
    def landing_root(self) -> str:
        return f"/Volumes/{self.catalog}/bronze/landing"

    @property
    def checkpoint_root(self) -> str:
        return f"/Volumes/{self.catalog}/bronze/checkpoints"

    def landing_dir(self, source_table: str) -> str:
        return f"{self.landing_root}/{BRONZE_SOURCES[source_table]}"

    def table(self, layer: str, name: str) -> str:
        return f"{self.catalog}.{layer}.{name}"
