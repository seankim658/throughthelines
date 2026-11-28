from __future__ import annotations

import argparse
import sys
from collections.abc import Collection
from dataclasses import replace
from pathlib import Path

from pipeline.config import (
    FetchConfig,
    ProjectConfig,
    ScopeSettings,
    load_fetch_config,
    published_scope,
)
from pipeline.core import SUPPORTED_STATES, SupportedStateCode
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
    return value


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


def print_warnings(warnings: list[str]) -> None:
    for warning in warnings:
        print(f"\twarn: {warning}", file=sys.stderr)


def print_warning_count(count: int) -> None:
    if count > 0:
        print(f"({count} warning(s))", file=sys.stderr)


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
    """Resolve the `--state` CLI argument against the built states."""
    configured: list[SupportedStateCode] = sorted(configured_states)
    if states_arg is None:
        return configured

    missing: list[SupportedStateCode] = [
        s for s in states_arg if s not in configured_states
    ]
    if missing:
        raise CliArgError(
            f"state(s) {missing} are not built states in [scope.chambers]; "
            f"built: {configured}"
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
    """Load sources.toml and resolve the --state argument against the built states.

    Every target state needs Lewis files, so one without them stops the step.
    """
    sources = load_sources(project_config)
    try:
        target_states: list[SupportedStateCode] = resolve_target_states(
            states_arg, project_config.scope.chambers.keys()
        )
    except CliArgError as e:
        raise CliError(f"error: {e}") from e
    without_lewis: list[SupportedStateCode] = [
        state for state in target_states if state not in sources.lewis.states
    ]
    if without_lewis:
        raise CliError(
            f"error: built state(s) {without_lewis} have no [lewis.states] "
            f"entry in {project_config.sources_config_path}"
        )
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


def add_include_unpublished_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--include-unpublished",
        action="store_true",
        help=(
            "Keep built states missing from scope.publish, for a local preview. "
            "publish refuses artifacts built this way."
        ),
    )


def release_config(
    project_config: ProjectConfig, args: argparse.Namespace
) -> ProjectConfig:
    """Return the config narrowed to published states, unless asked to keep all."""
    if args.include_unpublished:
        return project_config
    return replace(project_config, scope=published_scope(project_config.scope))


def print_unpublished(project_config: ProjectConfig, args: argparse.Namespace) -> None:
    """Name the built states this run left out, so a missing state is no surprise."""
    scope: ScopeSettings = project_config.scope
    left_out: list[str] = sorted(set(scope.chambers) - set(scope.publish))
    if args.include_unpublished:
        if left_out:
            print(f"\nIncluded unpublished: {', '.join(left_out)} (preview only)")
        return
    if left_out:
        print(
            f"\nLeft out (not in scope.publish): {', '.join(left_out)}. "
            "Pass --include-unpublished for a local preview."
        )
