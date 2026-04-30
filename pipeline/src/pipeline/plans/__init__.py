"""Plan metadata schema.

This subpackage defines the Pydantic models, cross-reference
validators, YAML loading from disk, scaffolding  for the plan-metadata YAML files.
"""

from pipeline.plans.models import PENDING, UNKNOWN, CourtCitation, Plan, Source
from pipeline.plans.validators import PlanSetValidationError, validate_plan_set
from pipeline.plans.loader import (
    LoadFailure,
    PlanLoadError,
    PlanSetLoadError,
    load_plan,
    load_plans_dir,
)
from pipeline.plans.scaffold import (
    ScaffoldGeneratorError,
    ScaffoldResult,
    scaffold_all,
    scaffold_one,
)
from pipeline.plans.stitch import (
    StitchError,
    StitchResult,
    stitch_state,
)

__all__ = [
    # Model
    "PENDING",
    "UNKNOWN",
    "CourtCitation",
    "Plan",
    "Source",
    # Validator
    "PlanSetValidationError",
    "validate_plan_set",
    # Loader
    "LoadFailure",
    "PlanLoadError",
    "PlanSetLoadError",
    "load_plan",
    "load_plans_dir",
    # Scaffold
    "ScaffoldGeneratorError",
    "ScaffoldResult",
    "scaffold_all",
    "scaffold_one",
    # Stitch
    "StitchError",
    "StitchResult",
    "stitch_state",
]
