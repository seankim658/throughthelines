"""Shared fixtures for the pipeline test suite."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT: Path = Path(__file__).resolve().parents[2]

PlanRecordFactory = Callable[..., dict[str, Any]]


@pytest.fixture
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture
def plan_record() -> PlanRecordFactory:
    """Return a factory for minimal valid plan records.

    Keyword arguments override or add fields, so each test states only the
    fields it is about.
    """

    def make(**overrides: Any) -> dict[str, Any]:
        record: dict[str, Any] = {
            "plan_id": "NC_113_2013",
            "state": "NC",
            "chamber": "congressional",
            "congress_start": 113,
            "congress_end": 114,
            "source_file": "district_geometry/lewis/NC/North Carolina_113_to_114.geojson",
            "source_commit": "f107b1b6c149c1b759cbb9b5bb14111a2355d6a1",
            "schema_version": 1,
        }
        record.update(overrides)
        return record

    return make
