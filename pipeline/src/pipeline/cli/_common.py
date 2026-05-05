from __future__ import annotations
import argparse
from typing import Collection, cast

from pipeline.core import StateCode, SUPPORTED_STATES


class CliArgError(Exception):
    """Raised when a CLI argument fails resolution against configured state."""


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
    configured_states: Collection[StateCode],
) -> list[StateCode]:
    """Resolve the `--state` CLI argument against the configured state set."""
    configured: list[StateCode] = sorted(configured_states)
    if states_arg is None:
        return configured

    missing: list[StateCode] = [s for s in states_arg if s not in configured_states]
    if missing:
        raise CliArgError(
            f"state(s) {missing} not configured in sources.toml; "
            f"available: {configured}"
        )

    return dedupe_states(states_arg)
