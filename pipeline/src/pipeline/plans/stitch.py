"""Stitch plan-metadata onto plan source-GeoJSON polygons.

For every polygon feature in a plan's source GeoJSON, attach the slim
subset of plan metadata defined by `Plan.to_feature_props()` as feature
properties. Emit one FeatureCollection per output tile-layer per state:

    - {state}_districts.geojson -> polygon features (district shapes)
    - {state}_labels.geojson    -> point features (one per district,
                                   positioned via representative_point)

The per-layer split lets the tiles step feed tippecanoe via the `-L name:file`
multi-layer syntax.

The stitched GeoJSON is an internal build artifact. It feeds two
downstream artifacts:

    - tippecanoe -> {STATE}.pmtiles  (map tiles)
    - spatial join with Census 2020 BEF -> block_lookup.json (address lookup)
"""

from __future__ import annotations
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from shapely.geometry import mapping, shape, Polygon, MultiPolygon
from shapely.geometry.base import BaseGeometry
from shapely.ops import polylabel, unary_union

from pipeline.plans.models import Plan
from pipeline.core import SupportedStateCode, write_json_atomic

# --- Errors ---


class StitchError(Exception):
    """Raised when stitching cannot complete."""


# --- Models ---


@dataclass(frozen=True)
class StitchResult:

    state: SupportedStateCode
    polygons_path: Path
    labels_path: Path
    plans_processed: int
    polygon_features_written: int
    label_features_written: int


# --- API ---


def stitch_state(
    plans: list[Plan], state: SupportedStateCode, raw_dir: Path, stitched_dir: Path
) -> StitchResult:
    """Stitch every plan for state into per-layer FeatureCollections.

    Writes one file per output tile-layer. Fails atomically.
    """
    state_plans: list[Plan] = [p for p in plans if p.state == state]
    if not state_plans:
        raise StitchError(f"no plans found for state {state}")

    all_polygons: list[dict[str, Any]] = []
    all_labels: list[dict[str, Any]] = []
    for plan in state_plans:
        polygons, labels = _stitch_one_plan(plan, raw_dir)
        all_polygons.extend(polygons)
        all_labels.extend(labels)

    stitched_dir.mkdir(parents=True, exist_ok=True)
    polygons_path: Path = stitched_dir / f"{state}_districts.geojson"
    labels_path: Path = stitched_dir / f"{state}_labels.geojson"

    write_json_atomic(
        polygons_path, {"type": "FeatureCollection", "features": all_polygons}
    )
    write_json_atomic(
        labels_path, {"type": "FeatureCollection", "features": all_labels}
    )

    return StitchResult(
        state=state,
        polygons_path=polygons_path,
        labels_path=labels_path,
        plans_processed=len(state_plans),
        polygon_features_written=len(all_polygons),
        label_features_written=len(all_labels),
    )


# --- Helpers ---


def _stitch_one_plan(
    plan: Plan, raw_dir: Path
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
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

    label_features: list[dict[str, Any]] = _compute_label_points(out)
    return out, label_features


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
            f"{plan_id}: feature[{feature_index}] has source properties that "
            f"collide with plan-metadata fields: {collisions}"
        )

    merged_props: dict[str, Any] = {**existing_props, **plan_props}
    return {**feature, "properties": merged_props}


def _compute_label_points(
    polygon_features: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Emit one Point feature per district for symbol-layer label placement."""
    by_district: dict[int, list[dict[str, Any]]] = {}

    for feat in polygon_features:
        district: Any = feat["properties"].get("district")
        if district is None:
            continue
        by_district.setdefault(int(district), []).append(feat)

    label_features: list[dict[str, Any]] = []
    for district_feats in by_district.values():
        geoms = [shape(f["geometry"]) for f in district_feats]
        unified = geoms[0] if len(geoms) == 1 else unary_union(geoms)
        anchor: Polygon = _largest_polygon(unified)
        point = polylabel(anchor, tolerance=0.001)

        props: dict[str, Any] = dict(district_feats[0]["properties"])
        props["feature_type"] = "label"

        label_features.append(
            {
                "type": "Feature",
                "properties": props,
                "geometry": mapping(point),
            }
        )

    return label_features


def _largest_polygon(geom: BaseGeometry) -> Polygon:
    if isinstance(geom, Polygon):
        return geom
    if isinstance(geom, MultiPolygon):
        return max(geom.geoms, key=lambda p: p.area)
    raise StitchError(
        f"expected Polygon or MultiPolygon for label anchor, "
        f"got {type(geom).__name__}"
    )
