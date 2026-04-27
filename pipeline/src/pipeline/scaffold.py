"""Generate placeholder plan-metadata YAMLs from Lewis GeoJSON files."""

from __future__ import annotations
import fnmatch
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import ValidationError

from pipeline.schema import Plan
from pipeline.state_codes import StateCode

ScaffoldStatus = Literal["wrote", "force", "skip", "fail"]

# --- Errors ---


class ScaffoldGeneratorError(Exception):
    """Raised when the generator produces a record that fails schema validation."""


# --- Models ---


@dataclass(frozen=True)
class ScaffoldResult:

    status: ScaffoldStatus
    plan_id: str | None
    source_path: Path
    dest_path: Path | None
    message: str | None = None


# --- API ---


def scaffold_all(
    lewis_dir: Path,
    plans_dir: Path,
    state: StateCode,
    lewis_commit_sha: str,
    patterns: list[str] | None = None,
    force: bool = False,
) -> list[ScaffoldResult]:
    if not lewis_dir.is_dir():
        raise FileNotFoundError(
            f"Lewis directory not found: {lewis_dir} "
            f"(did you run `pipeline fetch`?)"
        )

    plans_dir.mkdir(parents=True, exist_ok=True)
    lewis_files: list[Path] = sorted(lewis_dir.glob("*.geojson"))
    targeted: list[Path] = _filter_by_patterns(lewis_files, patterns)

    results: list[ScaffoldResult] = []
    for lewis_path in targeted:
        result: ScaffoldResult = scaffold_one(
            lewis_path, plans_dir, state, lewis_commit_sha, force
        )
        results.append(result)
    return results


def scaffold_one(
    lewis_path: Path,
    plans_dir: Path,
    state: StateCode,
    lewis_commit_sha: str,
    force: bool,
) -> ScaffoldResult:
    try:
        congress_start, congress_end = _read_congress_range(lewis_path)
    except _LewisReadError as e:
        return ScaffoldResult(
            status="fail",
            plan_id=None,
            source_path=lewis_path,
            dest_path=None,
            message=str(e),
        )

    plan_id: str = _build_plan_id(state, congress_start)
    dest_path: Path = plans_dir / f"{plan_id}.yaml"

    if dest_path.exists() and not force:
        return ScaffoldResult(
            status="skip", plan_id=plan_id, source_path=lewis_path, dest_path=dest_path
        )

    try:
        plan: Plan = _build_plan(
            plan_id=plan_id,
            state=state,
            congress_start=congress_start,
            congress_end=congress_end,
            lewis_filename=lewis_path.name,
            lewis_commit_sha=lewis_commit_sha,
        )
    except ValidationError as e:
        raise ScaffoldGeneratorError(
            f"generated record for {plan_id} failed schema validation: {e}"
        ) from e

    overwrite: bool = dest_path.exists()
    try:
        _write_yaml_atomic(dest_path, plan, lewis_filename=lewis_path.name)
    except OSError as e:
        return ScaffoldResult(
            status="fail",
            plan_id=plan_id,
            source_path=lewis_path,
            dest_path=dest_path,
            message=f"could not write file: {e}",
        )

    return ScaffoldResult(
        status="force" if overwrite else "wrote",
        plan_id=plan_id,
        source_path=lewis_path,
        dest_path=dest_path,
    )


# --- Lewis ---


class _LewisReadError(Exception):
    """Raised when a Lewis GeoJSON can't be parsed or has unexpected shape."""


def _read_congress_range(lewis_path: Path) -> tuple[int, int]:
    """Return (congress_start, congress_end) extracted from a Lewis GeoJSON."""
    try:
        with lewis_path.open(encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        raise _LewisReadError(f"invalid JSON: {e}") from e
    except OSError as e:
        raise _LewisReadError(f"could not read file: {e}") from e

    if not isinstance(data, dict):
        raise _LewisReadError("top-level GeoJSON must be a mapping")

    features = data.get("features")
    if not isinstance(features, list) or not features:
        raise _LewisReadError("GeoJSON has no features")

    starts: set[int] = set()
    ends: set[int] = set()
    for feature in features:
        if not isinstance(feature, dict):
            raise _LewisReadError("feature is not a mapping")
        props: Any = feature.get("properties")
        if not isinstance(props, dict):
            raise _LewisReadError("feature has no properties")
        starts.add(_coerce_congress_number(props.get("startcong"), "startcong"))
        ends.add(_coerce_congress_number(props.get("endcong"), "endcong"))

    if len(starts) != 1:
        raise _LewisReadError(
            f"startcong is not consistent across features: {sorted(starts)}"
        )
    if len(ends) != 1:
        raise _LewisReadError(
            f"endcong is not consistent across features: {sorted(ends)}"
        )

    return starts.pop(), ends.pop()


def _coerce_congress_number(value: Any, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise _LewisReadError(f"{field_name} is not numeric: {value!r}")
    as_int: int = int(value)
    if as_int != value:
        raise _LewisReadError(f"{field_name} is not a whole number: {value!r}")
    return as_int


# --- Plan-dict Construction ---


def _build_plan_id(state: StateCode, congress_start: int) -> str:
    year: int = 1787 + 2 * congress_start
    return f"{state}_{congress_start:03d}_{year:04d}"


def _build_plan(
    plan_id: str,
    state: StateCode,
    congress_start: int,
    congress_end: int,
    lewis_filename: str,
    lewis_commit_sha: str,
) -> Plan:
    return Plan(
        plan_id=plan_id,
        state=state,
        chamber="congressional",
        congress_start=congress_start,
        congress_end=congress_end,
        source_file=f"lewis/{lewis_filename}",
        source_commit=lewis_commit_sha,
        schema_version=1,
    )


# --- Helpers ---


def _write_yaml_atomic(dest_path: Path, plan: Plan, lewis_filename: str) -> None:
    plan_dict: dict[str, Any] = plan.model_dump(mode="json")
    header: str = (
        f"# Generated by `pipeline scaffold-plans` from data/raw/lewis/{lewis_filename}.\n"
        f"# Curation-sensitive fields are sentinels; replace with real values during Phase B.\n"
    )
    body: str = yaml.safe_dump(plan_dict, sort_keys=False, default_flow_style=False)

    tmp_path: Path = dest_path.with_suffix(dest_path.suffix + ".tmp")
    tmp_path.write_text(header + body, encoding="utf-8")
    os.replace(tmp_path, dest_path)


def _filter_by_patterns(
    lewis_files: list[Path], patterns: list[str] | None
) -> list[Path]:
    if not patterns:
        return list(lewis_files)
    return [
        path
        for path in lewis_files
        if any(fnmatch.fnmatch(path.name, pattern) for pattern in patterns)
    ]
