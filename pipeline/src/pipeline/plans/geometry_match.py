"""Match plans to the geometry sources that drew their districts."""

from pipeline.config import GeometrySource, ScopeSettings
from pipeline.plans.models import Plan


class PlanGeometryError(ValueError):
    """A plan matches its geometry sources in a way the build can't use."""


def plan_covers_congress(plan: Plan, congress: int, scope: ScopeSettings) -> bool:
    """Say whether `plan` governs `congress`.

    An open-ended plan runs to the end of scope.
    """
    plan_end: int = (
        plan.congress_end if plan.congress_end is not None else scope.congress_end
    )
    return plan.congress_start <= congress <= plan_end


def geometry_source_for_plan(
    plan: Plan, geometry_sources: list[GeometrySource], scope: ScopeSettings
) -> GeometrySource | None:
    """Return the geometry source whose Congress falls in `plan`'s range.

    Raise when more than one does, since every match would write the same
    plan file.
    """
    matches: list[GeometrySource] = [
        geometry_source
        for geometry_source in geometry_sources
        if geometry_source.state == plan.state
        and plan_covers_congress(plan, geometry_source.congress, scope)
    ]
    if len(matches) > 1:
        congresses: str = ", ".join(str(match.congress) for match in matches)
        raise PlanGeometryError(
            f"plan {plan.plan_id} matches geometry sources for Congresses "
            f"{congresses}; a plan takes at most one geometry source"
        )
    return matches[0] if matches else None
