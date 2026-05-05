"""Scope-oeverlap predicate for plan-metadata records.

A plan with `congress_end is None` is treated as still in effect
and extends forward indefinitely from `congress_start`.
"""

from __future__ import annotations

from pipeline.config import ScopeSettings
from pipeline.plans.models import Plan


def plan_in_scope(plan: Plan, scope: ScopeSettings) -> bool:
    if plan.congress_start > scope.congress_end:
        return False
    if plan.congress_end is None:
        return True
    return plan.congress_end >= scope.congress_start
