from dataclasses import dataclass
from typing import Literal, get_args

StateCode = Literal["NC"]
ChamberType = Literal["congressional"]
SUPPORTED_CHAMBERS: tuple[ChamberType, ...] = ("congressional",)


@dataclass(frozen=True)
class StateInfo:

    code: StateCode
    fips: str  # 2-digit Census FIPS
    name_upper: str  # TIGER URL slug


STATE_INFO: dict[StateCode, StateInfo] = {
    "NC": StateInfo(code="NC", fips="37", name_upper="NORTH_CAROLINA")
}

SUPPORTED_STATES: tuple[StateCode, ...] = tuple(STATE_INFO.keys())

assert set(STATE_INFO.keys()) == set(
    get_args(StateCode)
), "STATE_INFO keys and StateCode literal members must match"
