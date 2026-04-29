"""CLI entry point."""

from __future__ import annotations
import argparse
import sys
from pathlib import Path

from pipeline.config import (
    load_fetch_config,
    load_project_config,
    load_request_config,
)
from pipeline.config.project import ProjectConfig, ProjectConfigError
from pipeline.fetch import FetchError, fetch_all
from pipeline.paths import RepoRootNotFoundError, find_repo_root
from pipeline.scaffold import ScaffoldGeneratorError, ScaffoldResult, scaffold_all
from pipeline.schema import StateCode, PlanSetValidationError
from pipeline.state_codes import SUPPORTED_STATES
from pipeline.stitch import StitchError, stitch_state
from pipeline.loader import PlanLoadError, PlanSetLoadError, load_plans_dir
from pipeline.members import MembersBuildError, MembersBuildResult, build_members


def main(argv: list[str] | None = None) -> int:
    parser: argparse.ArgumentParser = _build_parser()
    args: argparse.Namespace = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 1

    try:
        repo_root: Path = find_repo_root()
    except RepoRootNotFoundError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    project_config_path: Path = repo_root / "config" / "project.toml"
    try:
        project_config = load_project_config(project_config_path, str(repo_root))
    except ProjectConfigError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    if args.command == "fetch":
        return _run_fetch(project_config)
    if args.command == "scaffold-plans":
        return _run_scaffold(project_config, args)
    if args.command == "stitch":
        return _run_stitch(project_config, args)
    if args.command == "members":
        return _run_members(project_config)

    parser.print_help()
    return 1


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pipeline", description="Build pipeline")
    subparsers = parser.add_subparsers(dest="command", metavar="COMMAND")

    # Fetch
    subparsers.add_parser("fetch", help="Download upstream sources to data/raw/.")

    # Scaffold
    scaffold_parser = subparsers.add_parser(
        "scaffold-plans",
        help="Generate placeholder plan-metadata YAMLs from Lewis GeoJSONs.",
    )
    scaffold_parser.add_argument(
        "--state",
        action="append",
        type=_validate_state,
        metavar="STATE",
        help=(
            "Two-letter state code to scaffold (repeatable, e.g., "
            "--state NC --state PA). If omitted, scaffolds every state "
            "configured in sources.toml."
        ),
    )
    scaffold_parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing YAMLs. Off by default.",
    )
    scaffold_parser.add_argument(
        "patterns",
        nargs="*",
        metavar="PATTERN",
        help=(
            "Optional glob patterns matched against Lewis filenames "
            "(e.g., '*119*'). Multiple patterns are OR-combined. "
            "If omitted, all files are processed."
        ),
    )

    # Stitch
    stitch_parser = subparsers.add_parser(
        "stitch",
        help="Stitch plan metadata onto Lewis polygons; emit per-state GeoJSON.",
    )
    stitch_parser.add_argument(
        "--state",
        action="append",
        type=_validate_state,
        metavar="STATE",
        help=(
            "Two-letter state code to stitch (repeatable). "
            "If omitted, stitches every state configured in sources.toml."
        ),
    )

    # Members
    subparsers.add_parser("members", help="Slice Voteview CSV into members.json.")

    return parser


# --- Helpers ---


def _validate_state(value: str) -> StateCode:
    if value not in SUPPORTED_STATES:
        raise argparse.ArgumentTypeError(
            f"unsupported state {value!r}; supported: {list(SUPPORTED_STATES)}"
        )
    return value  # type: ignore[return-value]


# --- Fetch ---


def _run_fetch(project_config: ProjectConfig) -> int:
    try:
        sources = load_fetch_config(project_config.sources_config_path)
        request = load_request_config(project_config.request_config_path)
    except (OSError, ValueError) as e:
        print(f"fetch failed: {e}", file=sys.stderr)
        return 2

    try:
        result = fetch_all(
            sources=sources,
            request_settings=request.request_settings,
            user_agent=project_config.user_agent,
            project_paths=project_config.project_paths,
        )
    except FetchError as e:
        print(f"fetch failed: {e}", file=sys.stderr)
        return 1

    fetched_count: int = sum(1 for f in result.files if f.status == "fetched")
    unchanged_count: int = sum(1 for f in result.files if f.status == "unchanged")

    for entry in result.files:
        marker: str = "->" if entry.status == "fetched" else "."
        print(f"\t{marker} {entry.status:9s} {entry.source_url}")

    print(
        f"\n{fetched_count} fetched, {unchanged_count} unchanged. "
        f"manifest: {result.manifest_path}"
    )
    return 0


# --- Scaffold ---


def _run_scaffold(project_config: ProjectConfig, args: argparse.Namespace) -> int:
    states_arg: list[StateCode] | None = args.state
    patterns: list[str] = list(args.patterns)
    force: bool = args.force

    try:
        sources = load_fetch_config(project_config.sources_config_path)
    except (OSError, ValueError) as e:
        print(f"error loading config: {e}", file=sys.stderr)
        return 2

    configured: list[StateCode] = sorted(sources.lewis.states.keys())
    if states_arg is None:
        target_states: list[StateCode] = configured
    else:
        missing: list[StateCode] = [
            s for s in states_arg if s not in sources.lewis.states
        ]
        if missing:
            print(
                f"error: state(s) {missing} not configured in sources.toml; "
                f"available: {configured}",
                file=sys.stderr,
            )
            return 2
        target_states = _dedupe_states(states_arg)

    counts: dict[str, int] = {"wrote": 0, "force": 0, "skip": 0, "fail": 0}

    for state in target_states:
        print(f"\n[{state}]")
        try:
            state_results: list[ScaffoldResult] = scaffold_all(
                lewis_dir=project_config.project_paths.lewis_dir / state,
                plans_dir=project_config.project_paths.plans_dir / state,
                state=state,
                lewis_commit_sha=sources.lewis.commit_sha,
                patterns=patterns or None,
                force=force,
            )
        except FileNotFoundError as e:
            print(f"\terror: {e}", file=sys.stderr)
            counts["fail"] += 1
            continue
        except ScaffoldGeneratorError as e:
            print(f"\tgenerator error: {e}", file=sys.stderr)
            counts["fail"] += 1
            continue

        state_counts: dict[str, int] = _print_scaffold_results(state_results, patterns)
        for key, value in state_counts.items():
            counts[key] += value

    print(
        f"\nTotal: {counts['wrote']} written, {counts['force']} overwritten, "
        f"{counts['skip']} skipped, {counts['fail']} failed."
    )

    return 1 if counts["fail"] > 0 else 0


def _dedupe_states(states: list[StateCode]) -> list[StateCode]:
    seen: set[StateCode] = set()
    result: list[StateCode] = []
    for state in states:
        if state not in seen:
            seen.add(state)
            result.append(state)
    return result


def _print_scaffold_results(
    results: list[ScaffoldResult], patterns: list[str]
) -> dict[str, int]:
    counts: dict[str, int] = {"wrote": 0, "force": 0, "skip": 0, "fail": 0}

    if not results:
        if patterns:
            print(f"\tno files matched patterns: {patterns}")
        else:
            print("\tno Lewis files found")
        return counts

    for result in results:
        counts[result.status] += 1
        marker: str = _status_marker(result.status)
        plan_id: str = result.plan_id or "?"
        dest: str = str(result.dest_path) if result.dest_path else "(none)"
        line: str = f"\t{marker} {result.status:5s} {plan_id:14s} → {dest}"
        if result.message:
            line += f"\t[{result.message}]"
        print(line)

    return counts


def _status_marker(status: str) -> str:
    return {"wrote": "→", "force": "↻", "skip": "·", "fail": "x"}.get(status, "?")


# Stitch


def _run_stitch(project_config: ProjectConfig, args: argparse.Namespace) -> int:
    states_arg: list[StateCode] | None = args.state

    try:
        sources = load_fetch_config(project_config.sources_config_path)
    except (OSError, ValueError) as e:
        print(f"error loading config: {e}", file=sys.stderr)
        return 2

    configured: list[StateCode] = sorted(sources.lewis.states.keys())
    if states_arg is None:
        target_states: list[StateCode] = configured
    else:
        missing: list[StateCode] = [
            s for s in states_arg if s not in sources.lewis.states
        ]
        if missing:
            print(
                f"error: state(s) {missing} not configured in sources.toml; "
                f"available: {configured}",
                file=sys.stderr,
            )
            return 2
        target_states = _dedupe_states(states_arg)

    paths = project_config.project_paths
    failed: bool = False

    for state in target_states:
        print(f"\n[{state}]")
        try:
            plans = load_plans_dir(paths.plans_dir / state)
        except (
            FileNotFoundError,
            NotADirectoryError,
            PlanLoadError,
            PlanSetLoadError,
            PlanSetValidationError,
        ) as e:
            print(f"\terror loading plans: {e}", file=sys.stderr)
            failed = True
            continue

        try:
            result = stitch_state(
                plans=plans,
                state=state,
                raw_dir=paths.raw_dir,
                stitched_dir=paths.stitched_dir,
            )
        except StitchError as e:
            print(f"\tstitch failed: {e}", file=sys.stderr)
            failed = True
            continue

        print(
            f"\t{result.plans_processed} plans, "
            f"{result.features_written} features → {result.output_path}"
        )

    return 1 if failed else 0


# --- Members ---


def _run_members(project_config: ProjectConfig) -> int:
    paths = project_config.project_paths
    voteview_csv_path: Path = paths.voteview_dir / "HSall_members.csv"

    try:
        result: MembersBuildResult = build_members(
            scope=project_config.scope,
            voteview_csv_path=voteview_csv_path,
            output_path=paths.members_file,
        )
    except MembersBuildError as e:
        print(f"members build failed: {e}", file=sys.stderr)
        return 1

    for warning in result.warnings:
        print(f"\twarn: {warning}", file=sys.stderr)

    print(
        f"\n{result.rows_read} rows read, {result.rows_in_scope} in scope, "
        f"{result.districts_covered} (state, congress, district) entries "
        f"→ {result.output_path}"
    )
    if result.warnings:
        print(f"({len(result.warnings)} warning(s))", file=sys.stderr)

    return 0
