from typing import Literal

StateCode = Literal["NC"]
SUPPORTED_STATES: tuple[StateCode, ...] = ("NC",)


ChamberType = Literal["congressional"]
SUPPORTED_CHAMBERS: tuple[ChamberType, ...] = ("congressional",)
