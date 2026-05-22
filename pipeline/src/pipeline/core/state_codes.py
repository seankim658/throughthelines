from __future__ import annotations
from dataclasses import dataclass
from typing import Literal, get_args

SupportedStateCode = Literal["NC"]
SupportedChamberType = Literal["congressional"]
SUPPORTED_CHAMBERS: tuple[SupportedChamberType, ...] = ("congressional",)


@dataclass(frozen=True)
class BBox:
    """WGS84 bounding box."""

    west: float
    south: float
    east: float
    north: float

    def as_pmtiles_arg(self) -> str:
        return f"{self.west},{self.south},{self.east},{self.north}"

    def buffered(self, degrees: float) -> BBox:
        if degrees < 0:
            raise ValueError(f"buffer must be non-negative, got {degrees}")
        return BBox(
            west=self.west - degrees,
            south=self.south - degrees,
            east=self.east + degrees,
            north=self.north + degrees,
        )


@dataclass(frozen=True)
class StateInfo:

    code: SupportedStateCode
    fips: str  # 2-digit Census FIPS
    name_upper: str  # TIGER URL slug
    display_name: str


STATE_INFO: dict[SupportedStateCode, StateInfo] = {
    "NC": StateInfo(
        code="NC", fips="37", name_upper="NORTH_CAROLINA", display_name="North Carolina"
    )
}

SUPPORTED_STATES: tuple[SupportedStateCode, ...] = tuple(STATE_INFO.keys())

if set(STATE_INFO.keys()) != set(get_args(SupportedStateCode)):
    raise RuntimeError(
        "STATE_INFO keys and StateCode literal members must match: "
        f"STATE_INFO has {sorted(STATE_INFO.keys())}, "
        f"StateCode has {sorted(get_args(SupportedStateCode))}"
    )

ALL_US_STATE_CODES: frozenset[str] = frozenset(
    {
        "AL",
        "AK",
        "AZ",
        "AR",
        "CA",
        "CO",
        "CT",
        "DE",
        "FL",
        "GA",
        "HI",
        "ID",
        "IL",
        "IN",
        "IA",
        "KS",
        "KY",
        "LA",
        "ME",
        "MD",
        "MA",
        "MI",
        "MN",
        "MS",
        "MO",
        "MT",
        "NE",
        "NV",
        "NH",
        "NJ",
        "NM",
        "NY",
        "NC",
        "ND",
        "OH",
        "OK",
        "OR",
        "PA",
        "RI",
        "SC",
        "SD",
        "TN",
        "TX",
        "UT",
        "VT",
        "VA",
        "WA",
        "WV",
        "WI",
        "WY",
        "DC",
    }
)
