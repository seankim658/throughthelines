from __future__ import annotations
import argparse
import sys

from pipeline.cli._common import CliArgError, resolve_target_states
from pipeline.blocks import BlocksBuildError, BlocksBuildResult, build_blocks
from pipeline.config import ProjectConfig, load_fetch_config
from pipeline.core import StateCode
from pipeline.plans import (
    PlanLoadError,
    PlanSetLoadError,
    PlanSetValidationError,
    load_plans_dir,
    plan_in_scope,
)


def run_blocks(project_config: ProjectConfig, args: argparse.Namespace) -> int:
    states_arg: list[StateCode] | None = args.state
    allow_missing: bool = bool(args.allow_missing)
    lewis_fallback: bool = bool(args.lewis_fallback)

    try:
        sources = load_fetch_config(project_config.sources_config_path)
    except (OSError, ValueError) as e:
        print(f"error loading config: {e}", file=sys.stderr)
        return 2

    try:
        target_states: list[StateCode] = resolve_target_states(
            states_arg, sources.lewis.states
        )
    except CliArgError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

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

        in_scope_plans = [p for p in plans if plan_in_scope(p, project_config.scope)]
        chambers = project_config.scope.chambers[state]
        for chamber in chambers:
            chamber_plans = [p for p in in_scope_plans if p.chamber == chamber]
            output_path = (
                paths.block_lookup_dir / f"block_lookup_{state}_{chamber}.json"
            )

            try:
                result: BlocksBuildResult = build_blocks(
                    plans=chamber_plans,
                    state=state,
                    chamber=chamber,
                    scope=project_config.scope,
                    project_paths=paths,
                    census_source=sources.census,
                    output_path=output_path,
                    allow_missing=allow_missing,
                    lewis_fallback=lewis_fallback,
                )
            except BlocksBuildError as e:
                print(f"\t[{chamber}] blocks build failed: {e}", file=sys.stderr)
                failed = True
                continue

            for warning in result.warnings:
                print(f"\t[{chamber}] warn: {warning}", file=sys.stderr)

            unsourced: list[int] = result.unsourced_congresses
            unsourced_label: str = (
                f", {len(unsourced)} unsourced congress(es): {unsourced}"
                if unsourced
                else ""
            )
            print(
                f"\t[{chamber}] {result.blocks_count} blocks, "
                f"{result.histories_count} unique histories"
                f"{unsourced_label} → {result.output_path}"
            )

    return 1 if failed else 0
