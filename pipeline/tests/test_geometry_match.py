from __future__ import annotations

import pytest
from conftest import PlanRecordFactory

from pipeline.config import GeometrySource, ScopeSettings
from pipeline.plans import Plan, PlanGeometryError, geometry_source_for_plan

_SCOPE = ScopeSettings(
    congress_start=113,
    congress_end=120,
    chambers={"NC": ["congressional"]},
    planned=[],
    publish=["NC"],
)


def _geometry_source(congress: int, provider: str = "ncga") -> GeometrySource:
    return GeometrySource(
        provider=provider,
        state="NC",
        congress=congress,
        url=f"https://example.org/{provider}/{congress}.zip",
        landing_url="https://example.org/landing",
        local_filename=f"{provider}_{congress}.zip",
        sha256="a" * 64,
        source_crs="EPSG:32119",
        district_field="DISTRICT",
    )


def test_plan_matches_the_source_inside_its_range(
    plan_record: PlanRecordFactory,
) -> None:
    plan = Plan.model_validate(plan_record())
    source = _geometry_source(114)

    assert geometry_source_for_plan(plan, [_geometry_source(116), source], _SCOPE) is (
        source
    )


def test_plan_with_no_source_in_range_matches_none(
    plan_record: PlanRecordFactory,
) -> None:
    plan = Plan.model_validate(plan_record())

    assert geometry_source_for_plan(plan, [_geometry_source(116)], _SCOPE) is None


def test_two_sources_for_one_plan_are_rejected(
    plan_record: PlanRecordFactory,
) -> None:
    plan = Plan.model_validate(plan_record())

    with pytest.raises(PlanGeometryError, match=r"NC_113_2013.*113.*114"):
        geometry_source_for_plan(
            plan, [_geometry_source(113), _geometry_source(114, "census")], _SCOPE
        )
