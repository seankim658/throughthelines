"""Normalize a zipped district shapefil into a WGS84 GeoJSON.

A provider-netrual utility, takes the upstream zip for a non-Lewis
authority and produces the GeoJSON for the stitch step to consume.
"""

from __future__ import annotations
import json
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from pipeline.core import write_json_atomic

if TYPE_CHECKING:
    from geopandas import GeoDataFrame

_TARGET_CRS: str = "EPSG:4326"

_DISTRICT_PROPERTY: str = "district"

# --- Errors ---


class GeometryNormalizeError(Exception):
    """Raised when normalizing a district shapefile cannot complete."""


# --- Models ---


@dataclass(frozen=True)
class GeometryNormalizeResult:

    output_path: Path
    feature_count: int
    distrct_count: int


# --- API ---


def normalize_geometry(
    input_zip: Path, source_crs: str, district_field: str, output_path: Path
) -> GeometryNormalizeResult:
    """Read a zipped shapefile and write a normalized WGS84 GeoJSON."""
    gdf = _read_shapefile_zip(input_zip)
    if len(gdf) == 0:
        raise GeometryNormalizeError(f"shapefile in {input_zip} has no features")

    _verify_crs(gdf, source_crs, input_zip)
    normalized = _build_normalized_frame(gdf, district_field, input_zip)

    write_json_atomic(output_path, json.loads(normalized.to_json()))

    return GeometryNormalizeResult(
        output_path=output_path,
        feature_count=int(len(normalized)),
        distrct_count=int(normalized[_DISTRICT_PROPERTY].nunique()),
    )


# --- Helpers ---


def _read_shapefile_zip(input_zip: Path) -> GeoDataFrame:
    import geopandas as gpd

    if not input_zip.exists():
        raise GeometryNormalizeError(
            f"geometry source not found at {input_zip} "
            f"(did you run `pipeline fetch`?)"
        )
    return gpd.read_file(f"zip://{input_zip}")


def _verify_crs(gdf: GeoDataFrame, source_crs: str, input_zip: Path) -> None:
    from pyproj import CRS
    from pyproj.exceptions import CRSError

    if gdf.crs is None:
        raise GeometryNormalizeError(
            f"shapefile in {input_zip} declares no CRS; expected {source_crs}"
        )
    try:
        expected_epsg: int | None = CRS.from_user_input(source_crs).to_epsg()
    except CRSError as e:
        raise GeometryNormalizeError(
            f"configured source_crs {source_crs!r} is not a recognized CRS: {e}"
        ) from e
    if expected_epsg is None:
        raise GeometryNormalizeError(
            f"configured source_crs {source_crs!r} has no EPSG code to compare against"
        )
    actual_epsg: int | None = CRS.from_user_input(gdf.crs).to_epsg()
    if actual_epsg != expected_epsg:
        raise GeometryNormalizeError(
            f"CRS mismatch in {input_zip}: shapefile declares EPSG:{actual_epsg}, "
            f"config expects EPSG:{expected_epsg} ({source_crs})"
        )


def _build_normalized_frame(
    gdf: GeoDataFrame, district_field: str, input_zip: Path
) -> GeoDataFrame:
    """Case the district field to int, repair geometry, reproject to WGS84."""
    import geopandas as gpd

    if district_field not in gdf.columns:
        raise GeometryNormalizeError(
            f"district field {district_field!r} not found in {input_zip}; "
            f"columns: {sorted(gdf.columns.tolist())}"
        )
    try:
        district = gdf[district_field].astype(int)
    except (ValueError, TypeError) as e:
        raise GeometryNormalizeError(
            f"district field {district_field!r} in {input_zip} is not "
            f"integer-castable: {e}"
        ) from e

    repaired_geometry = gdf.geometry.make_valid()
    normalized = gpd.GeoDataFrame(
        {_DISTRICT_PROPERTY: district}, geometry=repaired_geometry, crs=gdf.crs
    )

    return normalized.to_crs(_TARGET_CRS)
