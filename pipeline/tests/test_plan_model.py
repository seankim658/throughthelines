from __future__ import annotations

import pytest
from pydantic import ValidationError

from pipeline.plans import PENDING, Plan

from conftest import PlanRecordFactory

AAR_SOURCE: dict[str, str] = {
    "url": "https://redistricting.lls.edu/state/north-carolina/",
    "accessed": "2026-07-01",
    "source_code": "AAR",
}


def test_unfilled_curation_fields_default_to_pending(
    plan_record: PlanRecordFactory,
) -> None:
    plan = Plan.model_validate(plan_record())

    assert plan.origin == PENDING
    assert plan.struck_down == PENDING
    assert plan.enacted_date == PENDING
    assert plan.notes == PENDING
    assert plan.predecessor == PENDING
    assert plan.curation_status == PENDING


def test_unknown_sentinel_is_accepted_for_headline_fields(
    plan_record: PlanRecordFactory,
) -> None:
    plan = Plan.model_validate(plan_record(origin="unknown", struck_down="unknown"))

    assert plan.origin == "unknown"
    assert plan.struck_down == "unknown"


def test_unrecognized_field_is_rejected(plan_record: PlanRecordFactory) -> None:
    with pytest.raises(ValidationError, match="orign"):
        Plan.model_validate(plan_record(orign="court"))


def test_plan_id_state_must_match_state_field(plan_record: PlanRecordFactory) -> None:
    with pytest.raises(ValidationError, match="state prefix"):
        Plan.model_validate(plan_record(plan_id="VA_113_2013"))


def test_plan_id_congress_must_match_congress_start(
    plan_record: PlanRecordFactory,
) -> None:
    with pytest.raises(ValidationError, match="congress_start"):
        Plan.model_validate(plan_record(plan_id="NC_114_2015"))


def test_congress_end_before_start_is_rejected(plan_record: PlanRecordFactory) -> None:
    with pytest.raises(ValidationError, match="congress_end"):
        Plan.model_validate(plan_record(congress_end=112))


def test_open_ended_plan_is_accepted(plan_record: PlanRecordFactory) -> None:
    plan = Plan.model_validate(plan_record(congress_end=None))

    assert plan.congress_end is None


def test_plan_reference_accepts_null_pending_or_plan_id(
    plan_record: PlanRecordFactory,
) -> None:
    plan = Plan.model_validate(
        plan_record(predecessor=None, superseded_by="NC_115_2017")
    )

    assert plan.predecessor is None
    assert plan.superseded_by == "NC_115_2017"


def test_plan_reference_rejects_unknown_sentinel(
    plan_record: PlanRecordFactory,
) -> None:
    with pytest.raises(ValidationError, match="plan reference"):
        Plan.model_validate(plan_record(predecessor="unknown"))


def test_duplicate_source_code_is_rejected(plan_record: PlanRecordFactory) -> None:
    second_source: dict[str, str] = {**AAR_SOURCE, "url": "https://example.org/other"}

    with pytest.raises(ValidationError, match="duplicated: AAR"):
        Plan.model_validate(plan_record(sources=[AAR_SOURCE, second_source]))


def test_inline_citation_resolves_against_source_codes(
    plan_record: PlanRecordFactory,
) -> None:
    plan = Plan.model_validate(
        plan_record(sources=[AAR_SOURCE], notes="Drawn by the legislature [AAR].")
    )

    assert plan.notes == "Drawn by the legislature [AAR]."


def test_inline_citation_without_matching_code_is_rejected(
    plan_record: PlanRecordFactory,
) -> None:
    with pytest.raises(ValidationError, match=r"\[HARPER\]' matches no source_code"):
        Plan.model_validate(plan_record(sources=[AAR_SOURCE], notes="See [HARPER]."))


def test_malformed_inline_citation_is_rejected(plan_record: PlanRecordFactory) -> None:
    with pytest.raises(ValidationError, match="malformed citation"):
        Plan.model_validate(plan_record(sources=[AAR_SOURCE], notes="See [aar]."))


def test_feature_props_carry_only_the_click_time_subset(
    plan_record: PlanRecordFactory,
) -> None:
    plan = Plan.model_validate(plan_record(origin="court", struck_down=False))

    assert plan.to_feature_props() == {
        "plan_id": "NC_113_2013",
        "origin": "court",
        "struck_down": False,
        "curation_status": PENDING,
    }
