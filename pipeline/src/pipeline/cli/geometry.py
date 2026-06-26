from __future__ import annotations
import argparse
import sys
from pathlib import Path

from pipeline.cli._common import CliError, load_sources_and_states
from pipeline.config import (
    GeometrySource,
    ProjectConfig,
    ScopeSettings,
)
from pipeline.core import SupportedStateCode
from pipeline.geometry import GeometryNormalizeError, normalize_geometry
from pipeline.plans import (
    Plan,
    PlanLoadError,
    PlanSetLoadError,
    PlanSetValidationError,
    load_plans_dir,
    plan_in_scope,
)

# NOTE : should this be hardcoded here
_GEOMETRY_PATH_PREFIX: str = "district_geometry/"


def run_normalize_geometry(
    project_config: ProjectConfig, args: argparse.Namespace
) -> int:
    states_arg: list[SupportedStateCode] | None = args.state

    try:
        sources, target_states = load_sources_and_states(project_config, states_arg)
    except CliError as e:
        print(str(e), file=sys.stderr)
        return 2

    paths = project_config.project_paths
    scope = project_config.scope
    failed: bool = False
    normalized_count: int = 0

    for state in target_states:
        print(f"\n[{state}]")
        state_sources: list[GeometrySource] = [
            gs for gs in sources.geometry_sources if gs.state == state
        ]
        if not state_sources:
            print("\tno geometry sources")
            continue

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

        in_scope_plans = [p for p in plans if plan_in_scope(p, scope)]

        for geometry in state_sources:
            if _normalize_one(
                geometry,
                in_scope_plans,
                scope,
                paths.raw_dir,
                paths.district_geometry_dir,
            ):
                normalized_count += 1
            else:
                failed = True

    print(f"\n{normalized_count} geometry source(s) normalized.")
    return 1 if failed else 0


def _normalize_one(
    geometry: GeometrySource,
    in_scope_plans: list[Plan],
    scope: ScopeSettings,
    raw_dir: Path,
    district_geometry_dir: Path,
) -> bool:
    plan: Plan | None = _match_plan(geometry, in_scope_plans, scope)
    if plan is None:
        print(
            f"\terror: no in-scope plan covers Congress {geometry.congress} "
            f"(provider={geometry.provider!r}); cannot derive an output path",
            file=sys.stderr,
        )
        return False

    if Path(plan.source_file).is_absolute() or not plan.source_file.startswith(
        _GEOMETRY_PATH_PREFIX
    ):
        print(
            f"\terror: {plan.plan_id}.source_file {plan.source_file!r} is not a "
            f"relative path under {_GEOMETRY_PATH_PREFIX!r}",
            file=sys.stderr,
        )
        return False

    input_zip: Path = (
        district_geometry_dir
        / geometry.provider
        / geometry.state
        / geometry.local_filename
    )
    output_path: Path = raw_dir / plan.source_file

    try:
        result = normalize_geometry(
            input_zip=input_zip,
            source_crs=geometry.source_crs,
            district_field=geometry.district_field,
            output_path=output_path,
        )
    except GeometryNormalizeError as e:
        print(f"\t[{plan.plan_id}] normalize failed: {e}", file=sys.stderr)
        return False

    print(
        f"\t[{plan.plan_id}] {result.feature_count} features, "
        f"{result.distrct_count} distrcts → {result.output_path}"
    )
    return True


def _match_plan(
    geometry: GeometrySource, in_scope_plans: list[Plan], scope: ScopeSettings
) -> Plan | None:
    for plan in in_scope_plans:
        effective_end: int = (
            plan.congress_end if plan.congress_end is not None else scope.congress_end
        )
        if plan.congress_start <= geometry.congress <= effective_end:
            return plan
    return None
