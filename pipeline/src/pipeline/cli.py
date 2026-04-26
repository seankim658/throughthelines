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
from pipeline.schema import StateCode

SUPPORTED_STATES: tuple[StateCode, ...] = ("NC",)


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
        default="NC",
        type=_validate_state,
        help="Two-letter state code (default: NC). Currently only NC is supported.",
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
    except FetchError as e:
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
    state: StateCode = args.state
    patterns: list[str] = list(args.patterns)
    force: bool = args.force

    try:
        sources = load_fetch_config(project_config.sources_config_path)
    except (OSError, ValueError) as e:
        print(f"error loading config: {e}", file=sys.stderr)
        return 2

    try:
        results: list[ScaffoldResult] = scaffold_all(
            lewis_dir=project_config.project_paths.lewis_dir,
            plans_dir=project_config.project_paths.plans_dir / Path(state),
            state=state,
            lewis_commit_sha=sources.lewis.commit_sha,
            patterns=patterns or None,
            force=force,
        )
    except FileNotFoundError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    except ScaffoldGeneratorError as e:
        print(f"generator error: {e}", file=sys.stderr)
        return 1

    return _report_scaffold_results(results, patterns)


def _report_scaffold_results(results: list[ScaffoldResult], patterns: list[str]) -> int:
    if not results:
        if patterns:
            print(f"no files matched patterns: {patterns}")
        else:
            print("no Lewis files found")
        return 0

    counts: dict[str, int] = {"wrote": 0, "force": 0, "skip": 0, "fail": 0}
    for result in results:
        counts[result.status] += 1
        marker: str = _status_marker(result.status)
        plan_id: str = result.plan_id or "?"
        dest: str = str(result.dest_path) if result.dest_path else "(none)"
        line: str = f"\t{marker} {result.status:5s} {plan_id:14s} → {dest}"
        if result.message:
            line += f"\t[{result.message}]"
        print(line)

    summary: str = (
        f"\n{counts['wrote']} written, {counts['force']} overwritten, "
        f"{counts['skip']} skipped, {counts['fail']} failed."
    )
    print(summary)

    return 1 if counts["fail"] > 0 else 0


def _status_marker(status: str) -> str:
    return {"wrote": "→", "force": "↻", "skip": "·", "fail": "x"}.get(status, "?")
