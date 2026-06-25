"""File I/O for the block-lookup pipeline."""

from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Any, NamedTuple, Iterable, TYPE_CHECKING

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

# --- Helpers ---


def _centroids_from_columns(
    geoids: Iterable[Any],
    lons: Iterable[Any],
    lats: Iterable[Any],
    state_fips: str | None,
) -> dict[str, Centroid]:
    """Build a {geoid: Centroid} dict from three parallel column iterables."""
    centroids: dict[str, Centroid] = {}
    for geoid_raw, lon_raw, lat_raw in zip(geoids, lons, lats):
        geoid: str = str(geoid_raw)
        if state_fips is not None and not geoid.startswith(state_fips):
            continue
        centroids[geoid] = Centroid(lon=float(lon_raw), lat=float(lat_raw))
    return centroids


# --- API ---


def load_centroids(
    tabblock_path: Path,
    columns: TabblockColumns,
    state_fips: str | None = None,
) -> dict[str, Centroid]:
    """Read a tabblock zip and return {geoid: (lon, lat)} without loading geometry.

    The centroid columns (INTPTLAT/INTPTLON) are pre-computed attributes on every
    Census TIGER tabblock shapefile.
    """
    import pyogrio

    fields = [columns.geoid, columns.lon, columns.lat]
    df = pyogrio.read_dataframe(tabblock_path, columns=fields, read_geometry=False)
    return _centroids_from_columns(
        geoids=df[columns.geoid],
        lons=df[columns.lon],
        lats=df[columns.lat],
        state_fips=state_fips,
    )


def load_block_polygons(
    tabblock_path: Path, columns: TabblockColumns, state_fips: str | None = None
) -> tuple[GeoDataFrame, dict[str, Centroid]]:
    """Read a tabblock zip and return polygons + pre-computed centroids. The
    centroids are extracted from attribute columns (not computed from geometry).
    """
    import geopandas as gpd

    gdf: GeoDataFrame = gpd.read_file(
        tabblock_path, columns=[columns.geoid, columns.lon, columns.lat]
    )

    if state_fips is not None:
        keep = gdf[columns.geoid].astype(str).str.startswith(state_fips)
        gdf = gdf[keep].copy()

    centroids: dict[str, Centroid] = _centroids_from_columns(
        geoids=gdf[columns.geoid],
        lons=gdf[columns.lon],
        lats=gdf[columns.lat],
        state_fips=None,
    )
    return gdf, centroids


def load_plan_polygons(
    geojson_path: Path, district_property: str = "district"
) -> tuple[GeoDataFrame, str]:
    """Read a plan GeoJSON and return polygons with district codes."""
    import geopandas as gpd

    gdf: GeoDataFrame = gpd.read_file(geojson_path)

    if district_property not in gdf.columns:
        raise BlocksReadError(
            f"district property {district_property!r} not found in "
            f"{geojson_path}; columns: {sorted(gdf.columns.tolist())}"
        )

    gdf[district_property] = gdf[district_property].astype(int)

    return gdf, district_property


def load_delimited_assignment(
    zip_path: Path,
    inner_filename: str,
    state_fips: str,
    district_column: str,
    geoid_column: str | None = None,
    delimiter: str = ",",
) -> dict[str, int]:
    """Reads a delimited-assignment file from inside a zip.

    Covers both Census Block Equivalency (BEFs) and state-published block
    assignment files.

    Parameters
    ----------
    zip_path: Path
        Filesystem path to the upstream zip archive.
    inner_filename: str
        Name of the delimited file inside the zip
    state_fips
        Two-digit state FIPS code. Rows whose GEOID does not begin with this
        prefix are filtered out. National-scope files are reduced to the
        requested state.
    district_column: str
        Header name of the column that holds the district number, matched
        case-insensitively after trim.
    geoid_column
        Optional explicit GEOID column header (case-insensitive). When None
        (default), the GEOID column is auto-detected from the Census BEF
        alias set {"BLOCKID", "GEOID"}.
    delimiter: str
        Field separator.

    Returns
    -------
    A {block_geoid: district} dict containing only rows for the requested state.
    """
    import csv
    import zipfile

    geoid_aliases: frozenset[str] = (
        frozenset({geoid_column.strip().upper()})
        if geoid_column is not None
        else frozenset({"BLOCKID", "GEOID"})
    )
    district_column_upper: str = district_column.strip().upper()
    assignments: dict[str, int] = {}

    with zipfile.ZipFile(zip_path, "r") as zf:
        with zf.open(inner_filename) as raw:
            reader = csv.reader(
                (line.decode("utf-8-sig") for line in raw), delimiter=delimiter
            )
            header: list[str] = next(reader)

            geoid_idx: int | None = None
            district_idx: int | None = None
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
                    f"{inner_filename} within {zip_path}; "
                    f"header: {header}"
                )
            if district_idx is None:
                raise BlocksReadError(
                    f"could not find district column {district_column!r} in "
                    f"{inner_filename} within {zip_path}; "
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
