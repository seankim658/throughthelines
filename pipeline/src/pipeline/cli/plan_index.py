from __future__ import annotations
import sys

from pipeline.config import ProjectConfig
from pipeline.plans import PlanIndexBuildError, PlanIndexBuildResult, build_plan_index


def run_plan_index(project_config: ProjectConfig) -> int:
    paths = project_config.project_paths

    try:
        result: PlanIndexBuildResult = build_plan_index(
            scope=project_config.scope,
            plans_dir=paths.plans_dir,
            output_path=paths.plan_index_file,
        )
    except PlanIndexBuildError as e:
        print(f"plan-index build failed: {e}", file=sys.stderr)
        return 1

    for warning in result.warnings:
        print(f"\twarn: {warning}", file=sys.stderr)

    for state, count in sorted(result.per_state_counts.items()):
        print(f"\n[{state}]")
        print(f"\t{count} plans in scope")

    print(
        f"\n{result.states_count} state(s), {result.plans_count} plans total "
        f"→ {result.output_path}"
    )

    if result.warnings:
        print(f"({len(result.warnings)}) warning(s)", file=sys.stderr)

    return 0
