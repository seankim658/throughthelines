from __future__ import annotations
import argparse
import sys

from pipeline.cli._common import dedupe_states
from pipeline.config import ProjectConfig, load_fetch_config
from pipeline.core import StateCode
from pipeline.plans import (
    PlanLoadError,
    PlanSetLoadError,
    PlanSetValidationError,
    StitchError,
    load_plans_dir,
    stitch_state,
)


def run_stitch(project_config: ProjectConfig, args: argparse.Namespace) -> int:
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
        target_states = dedupe_states(states_arg)

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
