from __future__ import annotations
from typing import cast, Any
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


def resolve_target_states(
    states_arg: list[StateCode] | None,
    configured_states: dict[StateCode, Any],
) -> tuple[list[StateCode] | None, str | None]:
    """Resolve the `--state` CLI argument against the configured state set."""
    configured: list[StateCode] = sorted(configured_states.keys())
    if states_arg is None:
        return configured, None

    missing: list[StateCode] = [s for s in states_arg if s not in configured_states]
    if missing:
        message: str = (
            f"state(s) {missing} not configured in sources.toml; "
            f"available: {configured}"
        )
        return None, message

    return dedupe_states(states_arg), None
