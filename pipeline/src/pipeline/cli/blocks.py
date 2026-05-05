from __future__ import annotations
import argparse
import sys

from pipeline.blocks import BlocksBuildError, BlocksBuildResult, build_blocks
from pipeline.cli._common import resolve_target_states
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

    try:
        sources = load_fetch_config(project_config.sources_config_path)
    except (OSError, ValueError) as e:
        print(f"error loading config: {e}", file=sys.stderr)
        return 2

    target_states, error = resolve_target_states(states_arg, sources.lewis.states)
    if error is not None:
        print(f"error: {error}", file=sys.stderr)
        return 2
    assert target_states is not None

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

        plans = [p for p in plans if plan_in_scope(p, project_config.scope)]
        output_path = paths.block_lookup_dir / f"block_lookup_{state}.json"

        try:
            result: BlocksBuildResult = build_blocks(
                plans=plans,
                state=state,
                scope=project_config.scope,
                project_paths=paths,
                census_source=sources.census,
                output_path=output_path,
                allow_missing=allow_missing,
            )
        except BlocksBuildError as e:
            print(f"\tblocks build failed: {e}", file=sys.stderr)
            failed = True
            continue

        for warning in result.warnings:
            print(f"\twarn: {warning}", file=sys.stderr)

        unsourced: list[int] = result.unsourced_congresses
        unsourced_label: str = (
            f", {len(unsourced)} unsourced congress(es): {unsourced}"
            if unsourced
            else ""
        )
        print(
            f"\t{result.blocks_count} blocks, "
            f"{result.histories_count} unique histories"
            f"{unsourced_label} → {result.output_path}"
        )

    return 1 if failed else 0
