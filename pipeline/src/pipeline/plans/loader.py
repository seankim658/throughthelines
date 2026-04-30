"""Load and validate plan-metadata YAML files from disk.

Single entry point from the filesystem into the schema layer.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from pipeline.plans.models import Plan
from pipeline.plans.validators import validate_plan_set

YAML_EXTENSIONS: frozenset[str] = frozenset({".yaml", ".yml"})

# --- Errors ---


class PlanLoadError(Exception):

    def __init__(self, path: Path, message: str) -> None:
        self.path: Path = path
        self.message: str = message
        super().__init__(f"{path}: {message}")


class PlanSetLoadError(Exception):

    def __init__(self, failures: list[LoadFailure]) -> None:
        self.failures: list[LoadFailure] = failures
        summary: str = "\n".join(
            f"\t- {failure.path}: {failure.message}" for failure in failures
        )
        super().__init__(f"{len(failures)} plan file(s) failed to load:\n{summary}")


@dataclass(frozen=True)
class LoadFailure:

    path: Path
    message: str


# --- Single File Loader ---


def load_plan(path: Path) -> Plan:
    raw_text: str = _read_text(path)
    raw_data = _parse_yaml(path, raw_text)
    _require_mapping(path, raw_data)
    return _validate_against_schema(path, raw_data)


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError as e:
        raise PlanLoadError(path, "file not found") from e
    except OSError as e:
        raise PlanLoadError(path, f"could not read file: {e}") from e


def _parse_yaml(path: Path, raw_text: str) -> Any:
    try:
        return yaml.safe_load(raw_text)
    except yaml.YAMLError as e:
        raise PlanLoadError(path, f"invalid YAML: {e}") from e


def _require_mapping(path: Path, raw_data: Any) -> None:
    if raw_data is None:
        raise PlanLoadError(path, "file is empty")
    if not isinstance(raw_data, dict):
        raise PlanLoadError(
            path, f"top-level YAML must be a mapping, got {type(raw_data).__name__}"
        )


def _validate_against_schema(path: Path, raw_data: dict[str, Any]) -> Plan:
    try:
        return Plan.model_validate(raw_data)
    except ValidationError as e:
        raise PlanLoadError(path, f"schema validation failed:\n{e}") from e


# --- Directory Loader ---


def load_plans_dir(directory: Path) -> list[Plan]:
    if not directory.exists():
        raise FileNotFoundError(f"plans directory does not exist: {directory}")
    if not directory.is_dir():
        raise NotADirectoryError(f"plans path is not a directory: {directory}")

    yaml_paths: list[Path] = sorted(_find_yaml_files(directory))

    plans: list[Plan] = []
    failures: list[LoadFailure] = []

    for yaml_path in yaml_paths:
        try:
            plan: Plan = load_plan(yaml_path)
        except PlanLoadError as e:
            failures.append(LoadFailure(path=e.path, message=e.message))
            continue
        plans.append(plan)

    if failures:
        raise PlanSetLoadError(failures)

    validate_plan_set(plans)

    return sorted(plans, key=lambda plan: plan.plan_id)


def _find_yaml_files(directory: Path) -> list[Path]:
    return [
        entry
        for entry in directory.iterdir()
        if entry.is_file() and entry.suffix.lower() in YAML_EXTENSIONS
    ]
