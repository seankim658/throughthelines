from __future__ import annotations
import argparse
from pathlib import Path
from typing import Collection, cast

from pipeline.core import SupportedStateCode, SUPPORTED_STATES
from pipeline.config import FetchConfig, ProjectConfig, ScopeSettings, load_fetch_config
from pipeline.plans import (
    Plan,
    PlanLoadError,
    PlanSetLoadError,
    PlanSetValidationError,
    load_plans_dir,
    plan_in_scope,
)


class CliArgError(Exception):
    """Raised when a CLI argument fails resolution against configured state."""


class CliError(Exception):
    """A CLI failure carrying an already-formatted, user-facing message."""


def validate_state(value: str) -> SupportedStateCode:
    if value not in SUPPORTED_STATES:
        raise argparse.ArgumentTypeError(
            f"unsupported state {value!r}; supported: {list(SUPPORTED_STATES)}"
        )
    return cast(SupportedStateCode, value)


def dedupe_states(states: list[SupportedStateCode]) -> list[SupportedStateCode]:
    seen: set[SupportedStateCode] = set()
    result: list[SupportedStateCode] = []
    for state in states:
        if state not in seen:
            seen.add(state)
            result.append(state)
    return result


def status_marker(status: str) -> str:
    return {"wrote": "→", "force": "↻", "skip": "·", "fail": "x"}.get(status, "?")


def format_bytes(n: int) -> str:
    if n < 1024:
        return f"{n} B"
    if n < 1024 * 1024:
        return f"{n / 1024:.1f} KB"
    if n < 1024 * 1024 * 1024:
        return f"{n / (1024 * 1024):.1f} MB"
    return f"{n / (1024 * 1024 * 1024):.1f} GB"


def resolve_target_states(
    states_arg: list[SupportedStateCode] | None,
    configured_states: Collection[SupportedStateCode],
) -> list[SupportedStateCode]:
    """Resolve the `--state` CLI argument against the configured state set."""
    configured: list[SupportedStateCode] = sorted(configured_states)
    if states_arg is None:
        return configured

    missing: list[SupportedStateCode] = [
        s for s in states_arg if s not in configured_states
    ]
    if missing:
        raise CliArgError(
            f"state(s) {missing} not configured in sources.toml; "
            f"available: {configured}"
        )

    return dedupe_states(states_arg)


def load_sources(project_config: ProjectConfig) -> FetchConfig:
    """Load sources.toml."""
    try:
        return load_fetch_config(project_config.sources_config_path)
    except (OSError, ValueError) as e:
        raise CliError(f"error loading config: {e}") from e


def load_sources_and_states(
    project_config: ProjectConfig,
    states_arg: list[SupportedStateCode] | None,
) -> tuple[FetchConfig, list[SupportedStateCode]]:
    """Load sources.toml and resolve the --state argument against it."""
    sources = load_sources(project_config)
    try:
        target_states: list[SupportedStateCode] = resolve_target_states(
            states_arg, sources.lewis.states
        )
    except CliArgError as e:
        raise CliError(f"error: {e}") from e
    return sources, target_states


def load_in_scope_plans(
    plans_dir: Path, state: SupportedStateCode, scope: ScopeSettings
) -> list[Plan]:
    try:
        plans: list[Plan] = load_plans_dir(plans_dir / state)
    except (
        FileNotFoundError,
        NotADirectoryError,
        PlanLoadError,
        PlanSetLoadError,
        PlanSetValidationError,
    ) as e:
        raise CliError(f"\terror loading plans: {e}") from e
    return [p for p in plans if plan_in_scope(p, scope)]
