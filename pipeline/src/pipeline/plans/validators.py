"""Cross-reference validations across full set of plan YAMLs."""

from __future__ import annotations

from pipeline.plans.models import PENDING, Plan


class PlanSetValidationError(ValueError):
    """Raise when the full set of plans has a cross-reference problem."""


def validate_plan_set(plans: list[Plan]) -> None:
    """Validate a complete set of plan records for cross-reference integrity.

    Checks performed:
        1. Every plan_id is unique
        2. Every non-pending `predecessor` refers to an existing plan_id
        3. Every non-pending `superseded_by` refers to an existing plan_id
        4. If plan A.superseded_by == B, then plan B.predecessor == A
    """
    errors: list[str] = []

    _check_plan_ids_are_unique(plans, errors)
    plans_by_id: dict[str, Plan] = {plan.plan_id: plan for plan in plans}

    _check_references_resolve(plans, plans_by_id, errors)
    _check_successor_predecessor_symmetry(plans, plans_by_id, errors)

    if errors:
        raise PlanSetValidationError(
            "Cross-reference validation failed:\n - " + "\n - ".join(errors)
        )


# --- Helpers ---


def _check_plan_ids_are_unique(plans: list[Plan], errors: list[str]) -> None:
    seen: set[str] = set()
    duplicates: set[str] = set()

    for plan in plans:
        if plan.plan_id in seen:
            duplicates.add(plan.plan_id)
        seen.add(plan.plan_id)

    for duplicate in sorted(duplicates):
        errors.append(f"duplicate plan_id: {duplicate}")


def _check_references_resolve(
    plans: list[Plan], plans_by_id: dict[str, Plan], errors: list[str]
) -> None:
    for plan in plans:
        predecessor: str | None = _resolved_plan_id(plan.predecessor)
        if predecessor is not None and predecessor not in plans_by_id:
            errors.append(
                f"{plan.plan_id}.predecessor references unknown plan_id {predecessor!r}"
            )

        successor: str | None = _resolved_plan_id(plan.superseded_by)
        if successor is not None and successor not in plans_by_id:
            errors.append(
                f"{plan.plan_id}.superseded_by references unknown plan_id {successor!r}"
            )


def _check_successor_predecessor_symmetry(
    plans: list[Plan], plans_by_id: dict[str, Plan], errors: list[str]
) -> None:
    """Validate that A.superseded_by = B implies B.predecessor = A.

    Comparison rules:
        - If plan.superseded_by is pending or null, we have no claim to check
        - If the named successor is unknown to the plan set, that's caught by
          _check_references_resolve and skipped here
        - If successor.predecessor is null, the curator declared the successor
          has no predecessor, which is flagged as a contradiction
        - Otherwise, compare predecessor against plan.plan_id, flag as asymmetric
    """
    for plan in plans:
        successor_id: str | None = _resolved_plan_id(plan.superseded_by)
        if successor_id is None or successor_id not in plans_by_id:
            continue

        successor: Plan = plans_by_id[successor_id]
        if successor.predecessor == PENDING:
            continue

        if successor.predecessor != plan.plan_id:
            errors.append(
                f"asymmetric relation: {plan.plan_id}.superseded_by = {successor_id!r}, "
                f"but {successor_id}.predecessor = {successor.predecessor!r}"
            )


def _resolved_plan_id(value: str | None) -> str | None:
    """Return a real plan_id, or None if the reference is null or pending."""
    if value is None or value == PENDING:
        return None
    return value
