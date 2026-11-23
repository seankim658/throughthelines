"""Plan metadata schema.

This subpackage defines the Pydantic models, cross-reference
validators, YAML loading from disk, scaffolding  for the plan-metadata YAML files.
"""

from pipeline.plans.loader import (
    LoadFailure,
    PlanLoadError,
    PlanSetLoadError,
    load_plan,
    load_plans_dir,
)
from pipeline.plans.models import PENDING, UNKNOWN, CourtCitation, Plan, Source
from pipeline.plans.plan_index import (
    PlanIndexBuildError,
    PlanIndexBuildResult,
    build_plan_index,
)
from pipeline.plans.scaffold import (
    ScaffoldGeneratorError,
    ScaffoldResult,
    scaffold_all,
    scaffold_one,
)
from pipeline.plans.scope import plan_in_scope
from pipeline.plans.stitch import (
    StitchError,
    StitchResult,
    stitch_state,
)
from pipeline.plans.validators import PlanSetValidationError, validate_plan_set

__all__ = [
    "PENDING",
    "UNKNOWN",
    "CourtCitation",
    "LoadFailure",
    "Plan",
    "PlanIndexBuildError",
    "PlanIndexBuildResult",
    "PlanLoadError",
    "PlanSetLoadError",
    "PlanSetValidationError",
    "ScaffoldGeneratorError",
    "ScaffoldResult",
    "Source",
    "StitchError",
    "StitchResult",
    "build_plan_index",
    "load_plan",
    "load_plans_dir",
    "plan_in_scope",
    "scaffold_all",
    "scaffold_one",
    "stitch_state",
    "validate_plan_set",
]
