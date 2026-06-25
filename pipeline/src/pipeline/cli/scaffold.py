from __future__ import annotations
import argparse
import sys

from pipeline.cli._common import CliArgError, resolve_target_states, status_marker
from pipeline.config import ProjectConfig, load_fetch_config
from pipeline.core import SupportedStateCode
from pipeline.plans import ScaffoldGeneratorError, ScaffoldResult, scaffold_all


def run_scaffold(project_config: ProjectConfig, args: argparse.Namespace) -> int:
    states_arg: list[SupportedStateCode] | None = args.state
    patterns: list[str] = list(args.patterns)
    force: bool = args.force

    try:
        sources = load_fetch_config(project_config.sources_config_path)
    except (OSError, ValueError) as e:
        print(f"error loading config: {e}", file=sys.stderr)
        return 2

    try:
        target_states: list[SupportedStateCode] = resolve_target_states(
            states_arg, sources.lewis.states
        )
    except CliArgError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    counts: dict[str, int] = {"wrote": 0, "force": 0, "skip": 0, "fail": 0}

    for state in target_states:
        print(f"\n[{state}]")
        try:
            state_results: list[ScaffoldResult] = scaffold_all(
                lewis_dir=project_config.project_paths.lewis_dir / state,
                plans_dir=project_config.project_paths.plans_dir / state,
                state=state,
                lewis_commit_sha=sources.lewis.commit_sha,
                raw_dir=project_config.project_paths.raw_dir,
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
        marker: str = status_marker(result.status)
        plan_id: str = result.plan_id or "?"
        dest: str = str(result.dest_path) if result.dest_path else "(none)"
        line: str = f"\t{marker} {result.status:5s} {plan_id:14s} → {dest}"
        if result.message:
            line += f"\t[{result.message}]"
        print(line)

    return counts
