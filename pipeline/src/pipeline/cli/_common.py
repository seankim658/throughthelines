from __future__ import annotations
from typing import cast
import argparse

from pipeline.core import StateCode, SUPPORTED_STATES


def validate_state(value: str) -> StateCode:
    if value not in SUPPORTED_STATES:
        raise argparse.ArgumentTypeError(
            f"unsupported state {value!r}; supported: {list(SUPPORTED_STATES)}"
        )
    return cast(StateCode, value)


def dedupe_states(states: list[StateCode]) -> list[StateCode]:
    seen: set[StateCode] = set()
    result: list[StateCode] = []
    for state in states:
        if state not in seen:
            seen.add(state)
            result.append(state)
    return result


def status_marker(status: str) -> str:
    return {"wrote": "→", "force": "↻", "skip": "·", "fail": "x"}.get(status, "?")
