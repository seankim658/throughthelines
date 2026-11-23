from __future__ import annotations

from pathlib import Path

import pytest

from pipeline.plans import (
    Plan,
    PlanSetValidationError,
    load_plans_dir,
    validate_plan_set,
)

from conftest import PlanRecordFactory


def _plan_2013(plan_record: PlanRecordFactory, **overrides: object) -> Plan:
    return Plan.model_validate(plan_record(**overrides))


def _plan_2017(plan_record: PlanRecordFactory, **overrides: object) -> Plan:
    return Plan.model_validate(
        plan_record(
            plan_id="NC_115_2017",
            congress_start=115,
            congress_end=116,
            **overrides,
        )
    )


def test_linked_predecessor_and_successor_pass(plan_record: PlanRecordFactory) -> None:
    plans: list[Plan] = [
        _plan_2013(plan_record, superseded_by="NC_115_2017"),
        _plan_2017(plan_record, predecessor="NC_113_2013"),
    ]

    validate_plan_set(plans)


def test_duplicate_plan_id_is_rejected(plan_record: PlanRecordFactory) -> None:
    plans: list[Plan] = [_plan_2013(plan_record), _plan_2013(plan_record)]

    with pytest.raises(PlanSetValidationError, match="NC_113_2013"):
        validate_plan_set(plans)


def test_reference_to_missing_plan_is_rejected(plan_record: PlanRecordFactory) -> None:
    plans: list[Plan] = [_plan_2013(plan_record, superseded_by="NC_115_2017")]

    with pytest.raises(PlanSetValidationError, match="NC_115_2017"):
        validate_plan_set(plans)


def test_successor_must_name_its_predecessor(plan_record: PlanRecordFactory) -> None:
    plans: list[Plan] = [
        _plan_2013(plan_record, superseded_by="NC_115_2017"),
        _plan_2017(plan_record, predecessor=None),
    ]

    with pytest.raises(PlanSetValidationError):
        validate_plan_set(plans)


def test_pending_references_are_not_checked(plan_record: PlanRecordFactory) -> None:
    plans: list[Plan] = [_plan_2013(plan_record), _plan_2017(plan_record)]

    validate_plan_set(plans)


def test_every_plan_directory_in_the_repo_validates(repo_root: Path) -> None:
    state_dirs: list[Path] = sorted(
        path for path in (repo_root / "data" / "plans").iterdir() if path.is_dir()
    )

    assert state_dirs
    for state_dir in state_dirs:
        validate_plan_set(load_plans_dir(state_dir))
