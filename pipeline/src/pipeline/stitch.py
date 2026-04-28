"""Stitch plan-metadata onto Lewis GeoJSON polygons.

For every polygon feature in a plan's source GeoJSON, attach the slim
subset of plan metadata defined by `Plan.to_feature_props()` as feature
properties. Concatenate every plan's stitched features into one
FeatureCollection per state, written to data/derived/stitched/.

The stitched GeoJSON is an internal build artifact. It feeds two
downstream artifacts:

    - tippecanoe -> {STATE}.pmtiles  (map tiles)
    - spatial join with Census 2020 BAF -> block_lookup.json (address lookup)
"""

from __future__ import annotations
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pipeline.schema import Plan
from pipeline.state_codes import StateCode

# --- Errors ---


class StitchError(Exception):
    """Raised when stitching cannot complete."""


# --- Models ---


@dataclass(frozen=True)
class StitchResult:

    state: StateCode
    output_path: Path
    plans_processed: int
    features_written: int


# --- API ---


def stitch_state(
    plans: list[Plan], state: StateCode, raw_dir: Path, stitched_dir: Path
) -> StitchResult:
    """Stitch every plan for state into one FeatureCollection.

    Fails atomically, if any plan's source GeoJSON is missing, malformed,
    or has a property collision no output is written.
    """
    state_plans: list[Plan] = [p for p in plans if p.state == state]
    if not state_plans:
        raise StitchError(f"no plans found for state {state}")

    all_features: list[dict[str, Any]] = []
    for plan in state_plans:
        plan_features: list[dict[str, Any]] = _stitch_one_plan(plan, raw_dir)
        all_features.extend(plan_features)

    feature_collection: dict[str, Any] = {
        "type": "FeatureCollection",
        "features": all_features,
    }

    stitched_dir.mkdir(parents=True, exist_ok=True)
    output_path: Path = stitched_dir / f"{state}.geojson"
    _write_json_atomic(output_path, feature_collection)

    return StitchResult(
        state=state,
        output_path=output_path,
        plans_processed=len(state_plans),
        features_written=len(all_features),
    )


# --- Helpers ---


def _stitch_one_plan(plan: Plan, raw_dir: Path) -> list[dict[str, Any]]:
    source_path: Path = raw_dir / plan.source_file
    if not source_path.exists():
        raise StitchError(
            f"{plan.plan_id}: source file not found at {source_path} "
            f"(did you run `pipeline fetch`?)"
        )

    try:
        with source_path.open(encoding="utf-8") as f:
            data: Any = json.load(f)
    except json.JSONDecodeError as e:
        raise StitchError(f"{plan.plan_id}: invalid JSON in {source_path}: {e}") from e
    except OSError as e:
        raise StitchError(f"{plan.plan_id}: could not read {source_path}: {e}") from e

    if not isinstance(data, dict):
        raise StitchError(
            f"{plan.plan_id}: top-level GeoJSON in {source_path} is not a mapping"
        )
    features = data.get("features")
    if not isinstance(features, list) or not features:
        raise StitchError(f"{plan.plan_id}: GeoJSON has no features in {source_path}")

    plan_props: dict[str, Any] = plan.to_feature_props()

    out: list[dict[str, Any]] = []
    for idx, feature in enumerate(features):
        if not isinstance(feature, dict):
            raise StitchError(
                f"{plan.plan_id}: feature at index {idx} is not a mapping"
            )
        out.append(_attach_plan_props(feature, plan_props, plan.plan_id, idx))
    return out


def _attach_plan_props(
    feature: dict[str, Any],
    plan_props: dict[str, Any],
    plan_id: str,
    feature_index: int,
) -> dict[str, Any]:
    existing_props = feature.get("properties")
    if existing_props is None:
        existing_props = {}
    if not isinstance(existing_props, dict):
        raise StitchError(
            f"{plan_id}: feature[{feature_index}].properties is not a mapping"
        )

    collisions: list[str] = sorted(k for k in plan_props if k in existing_props)
    if collisions:
        raise StitchError(
            f"{plan_id}: feature[{feature_index}] has Lewis properties that "
            f"collide with plan-metadata fields: {collisions}"
        )

    merged_props: dict[str, Any] = {**existing_props, **plan_props}
    return {**feature, "properties": merged_props}


def _write_json_atomic(dest_path: Path, payload: Any) -> None:
    tmp_path: Path = dest_path.with_suffix(dest_path.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, separators=(",", ":"))
    os.replace(tmp_path, dest_path)
