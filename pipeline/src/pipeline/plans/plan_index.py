"""Build plan_index.json, the full plan-metadata index for the frontend.

Reads every plan-metadata YAML in scope, serializes the full plan records
into a single JSON file keyed by state and plan_id. Frontend uses this
for timeline rendering, side-panel details, per-district landing pages,
data export, and metadata-completeness indicators.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pipeline.config import ScopeSettings
from pipeline.core import SupportedStateCode, write_json_atomic
from pipeline.plans.models import Plan
from pipeline.plans.loader import PlanLoadError, PlanSetLoadError, load_plans_dir
from pipeline.plans.validators import PlanSetValidationError
from pipeline.plans.scope import plan_in_scope

_OUTPUT_SCHEMA_VERSION: int = 1

# Fields that are build-pipeline internals and should not be exposed to the frontend
_EXCLUDED_FIELDS: frozenset[str] = frozenset({"source_file", "source_commit"})

# --- Errors ---


class PlanIndexBuildError(Exception):
    """Raised when the plan_index.json build cannot complete."""


# --- Models ---


@dataclass(frozen=True)
class _StatePlansResult:
    """Result of loading and filtering plans for a single state."""

    records: dict[str, dict[str, Any]]
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class PlanIndexBuildResult:

    output_path: Path
    states_count: int
    plans_count: int
    per_state_counts: dict[str, int] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


# --- Internals ---


def _plan_to_record(plan: Plan) -> dict[str, Any]:
    """Serialize a Plan to a dict, dropping build internal fields."""
    record: dict[str, Any] = plan.model_dump(mode="json")
    for key in _EXCLUDED_FIELDS:
        record.pop(key, None)
    return record


def _load_state_plans(
    plans_dir: Path, state: SupportedStateCode, scope: ScopeSettings
) -> _StatePlansResult:
    """Load and filter plans for one state."""
    state_dir: Path = plans_dir / state
    warnings: list[str] = []

    if not state_dir.is_dir():
        warnings.append(f"no polan directory for state {state} at {state_dir}")
        return _StatePlansResult(records={}, warnings=warnings)

    try:
        all_plans: list[Plan] = load_plans_dir(state_dir)
    except (PlanLoadError, PlanSetLoadError, PlanSetValidationError) as e:
        raise PlanIndexBuildError(f"failed to load plans for {state}: {e}") from e

    in_scope: list[Plan] = [p for p in all_plans if plan_in_scope(p, scope)]

    if not in_scope:
        warnings.append(f"no plans in scope for state {state}")

    records: dict[str, dict[str, Any]] = {}
    for plan in in_scope:
        records[plan.plan_id] = _plan_to_record(plan)

    return _StatePlansResult(records=records, warnings=warnings)


# --- API ---


def build_plan_index(
    scope: ScopeSettings, plans_dir: Path, output_path: Path
) -> PlanIndexBuildResult:
    """Build plan index JSON covering every state in scope."""
    states: list[SupportedStateCode] = sorted(scope.chambers.keys())

    all_warnings: list[str] = []
    plans_by_state: dict[str, dict[str, dict[str, Any]]] = {}
    per_state_counts: dict[str, int] = {}
    total_plans: int = 0

    for state in states:
        result = _load_state_plans(plans_dir, state, scope)
        all_warnings.extend(result.warnings)
        if result.records:
            plans_by_state[state] = result.records
            per_state_counts[state] = len(result.records)
            total_plans += len(result.records)

    output: dict[str, Any] = {
        "schema_version": _OUTPUT_SCHEMA_VERSION,
        "plans": plans_by_state,
    }

    write_json_atomic(output_path, output)

    return PlanIndexBuildResult(
        output_path=output_path,
        states_count=len(plans_by_state),
        plans_count=total_plans,
        per_state_counts=per_state_counts,
        warnings=all_warnings,
    )
