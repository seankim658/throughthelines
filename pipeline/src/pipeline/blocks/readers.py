"""File I/O for the block-lookup pipeline."""

from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import NamedTuple, TYPE_CHECKING

if TYPE_CHECKING:
    from geopandas import GeoDataFrame

# --- Errors ---


class BlocksReadError(Exception):
    """Raised when a reader cannot parse an upstream file."""


# --- Models ---


class Centroid(NamedTuple):
    """Pre-computed internal-point centroid from a Census TIGER tabblock."""

    lon: float
    lat: float


@dataclass(frozen=True)
class TabblockColumns:
    """Column names for a single vintage of Census TIGER tabblock shapefiles."""

    geoid: str
    lon: str
    lat: str


TABBLOCK_COLUMNS: dict[str, TabblockColumns] = {
    "v2020": TabblockColumns(geoid="GEOID20", lon="INTPTLON20", lat="INTPTLAT20"),
    "v2010": TabblockColumns(geoid="GEOID10", lon="INTPTLON10", lat="INTPTLAT10"),
    "v2000": TabblockColumns(geoid="BLKIDFP00", lon="INTPTLON00", lat="INTPTLAT00"),
}


# --- API ---


def load_centroids(
    tabblock_path: Path,
    columns: TabblockColumns,
    state_fips: str | None = None,
) -> dict[str, Centroid]:
    """Read a tabblock zip and return {geoid: (lon, lat)} without loading geometry.

    The centroid columns (INTPTLAT/INTPTLON) are pre-computed attribtues on every
    Census TIGER tabblock shapefile.
    """
    import pyogrio

    fields = [columns.geoid, columns.lon, columns.lat]
    df = pyogrio.read_dataframe(tabblock_path, columns=fields, read_geometry=False)

    centroids: dict[str, Centroid] = {}
    for geoid_raw, lon_raw, lat_raw in zip(
        df[columns.geoid], df[columns.lon], df[columns.lat]
    ):
        geoid: str = str(geoid_raw)
        if state_fips is not None and not geoid.startswith(state_fips):
            continue
        centroids[geoid] = Centroid(lon=float(lon_raw), lat=float(lat_raw))

    return centroids


def load_block_polygons(
    tabblock_path: Path, columns: TabblockColumns, state_fips: str | None = None
) -> tuple[GeoDataFrame, dict[str, Centroid]]:
    """Read a tabblock zip and return polygons + pre-comptued centroids. The
    centroids are extracted from attribute columns (not computed from geometry).
    """
    import geopandas as gpd

    gdf: GeoDataFrame = gpd.read_file(
        tabblock_path, columns=[columns.geoid, columns.lon, columns.lat]
    )

    if state_fips is not None:
        keep = gdf[columns.geoid].astype(str).str.startswith(state_fips)
        gdf = gdf[keep].copy()

    centroids: dict[str, Centroid] = {}
    for geoid_raw, lon_raw, lat_raw in zip(
        gdf[columns.geoid], gdf[columns.lon], gdf[columns.lat]
    ):
        centroids[str(geoid_raw)] = Centroid(lon=float(lon_raw), lat=float(lat_raw))

    return gdf, centroids


def load_lewis_polygons(
    geojson_path: Path, district_property: str = "district"
) -> tuple[GeoDataFrame, str]:
    """Read a Lewis plan GeoJSON and return polygons with district codes."""
    import geopandas as gpd

    gdf: GeoDataFrame = gpd.read_file(geojson_path)

    if district_property not in gdf.columns:
        raise BlocksReadError(
            f"district property {district_property!r} not found in "
            f"{geojson_path}; columns: {sorted(gdf.columns.tolist())}"
        )

    gdf[district_property] = gdf[district_property].astype(int)

    return gdf, district_property


def load_bef(
    bef_zip_path: Path, inner_filename: str, state_fips: str, district_column: str
) -> dict[str, int]:
    """Reads a Census BEF zip and return {block_geoid: district} for one state."""
    import csv
    import zipfile

    geoid_aliases: frozenset[str] = frozenset({"BLOCKID", "GEOID"})
    assignments: dict[str, int] = {}

    with zipfile.ZipFile(bef_zip_path, "r") as zf:
        with zf.open(inner_filename) as raw:
            reader = csv.reader((line.decode("utf-8") for line in raw), delimiter=",")
            header: list[str] = next(reader)

            geoid_idx: int | None = None
            district_idx: int | None = None
            district_column_upper: str = district_column.strip().upper()
            for i, col in enumerate(header):
                col_stripped: str = col.strip().upper()
                if col_stripped in geoid_aliases:
                    geoid_idx = i
                elif col_stripped == district_column_upper:
                    district_idx = i

            if geoid_idx is None:
                raise BlocksReadError(
                    f"could not identify block-GEOID column "
                    f"(expected one of {sorted(geoid_aliases)}) in "
                    f"{inner_filename} within {bef_zip_path}; "
                    f"header: {header}"
                )
            if district_idx is None:
                raise BlocksReadError(
                    f"could not find district column {district_column!r} in "
                    f"{inner_filename} within {bef_zip_path}; "
                    f"header: {header}"
                )

            for row in reader:
                if len(row) <= max(geoid_idx, district_idx):
                    continue
                geoid: str = row[geoid_idx].strip()
                if not geoid.startswith(state_fips):
                    continue
                district_raw: str = row[district_idx].strip()
                try:
                    assignments[geoid] = int(district_raw)
                except ValueError:
                    continue

    return assignments
