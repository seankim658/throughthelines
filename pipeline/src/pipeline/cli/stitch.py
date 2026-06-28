from __future__ import annotations
import argparse
import sys

from pipeline.cli._common import CliError, load_in_scope_plans, load_sources_and_states
from pipeline.config import ProjectConfig
from pipeline.core import SupportedStateCode
from pipeline.plans import (
    StitchError,
    stitch_state,
)


def run_stitch(project_config: ProjectConfig, args: argparse.Namespace) -> int:
    states_arg: list[SupportedStateCode] | None = args.state

    try:
        _, target_states = load_sources_and_states(project_config, states_arg)
    except CliError as e:
        print(str(e), file=sys.stderr)
        return 2

    paths = project_config.project_paths
    failed: bool = False

    for state in target_states:
        print(f"\n[{state}]")
        try:
            plans = load_in_scope_plans(paths.plans_dir, state, project_config.scope)
        except CliError as e:
            print(str(e), file=sys.stderr)
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

        print(f"\t{result.plans_processed} plans:")
        print(
            f"\t  {result.polygon_features_written} polygons → {result.polygons_path}"
        )
        print(f"\t  {result.label_features_written} labels → {result.labels_path}")

    return 1 if failed else 0
