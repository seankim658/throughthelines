"""Match plans to the geometry sources that drew their districts."""

from pipeline.config import GeometrySource, ScopeSettings
from pipeline.plans.models import Plan


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
    """Return the geometry source whose Congress falls in `plan`'s range."""
    for geometry_source in geometry_sources:
        if geometry_source.state != plan.state:
            continue
        if plan_covers_congress(plan, geometry_source.congress, scope):
            return geometry_source
    return None
