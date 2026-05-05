"""Spatial join primitives for the block-lookup pipeline."""

from __future__ import annotations
from typing import TYPE_CHECKING, NamedTuple

from pipeline.blocks.readers import Centroid

if TYPE_CHECKING:
    import geopandas as gpd

# --- Models ---


class CrossDecadeResult(NamedTuple):
    """Result of spatially joining source centroids against target-decade polygons."""

    linkage: dict[str, str]  # {source_geoid: target_geoid}
    target_centroids: dict[
        str, Centroid
    ]  # pre-computed centroids from the target decade
    unmatched: list[str]  # source GEOIDs that didn't land in any target polygon


# --- API ---


def cross_decade_join(
    source_centroids: dict[str, Centroid],
    target_polygons: gpd.GeoDataFrame,
    target_geoid_col: str,
    target_centroids: dict[str, Centroid],
) -> CrossDecadeResult:
    """Spatial-join source centroids against target-decade block polygons.

    For each source centroid, finds which target-decade polygon it falls
    inside, producing a {sosurce_geoid: target_geoid} linkage.
    """
    import geopandas as gpd
    from shapely import Point

    source_geoids: list[str] = list(source_centroids.keys())
    points_gdf = gpd.GeoDataFrame(
        {"source_geoid": source_geoids},
        geometry=[Point(c.lon, c.lat) for c in source_centroids.values()],
        crs=target_polygons.crs,
    )

    joined: gpd.GeoDataFrame = gpd.sjoin(
        points_gdf, target_polygons, how="left", predicate="within"
    )

    # A centroid on a polygon boundary can match multiple polygons.
    # Keep first match for simplicity.
    joined = joined.drop_duplicates(subset="source_geoid", keep="first")

    has_match = joined["index_right"].notna()
    matched = joined[has_match]
    linkage: dict[str, str] = dict(
        zip(matched["source_geoid"].astype(str), matched[target_geoid_col].astype(str))
    )
    unmatched: list[str] = joined[~has_match]["source_geoid"].tolist()

    return CrossDecadeResult(
        linkage=linkage, target_centroids=target_centroids, unmatched=unmatched
    )


def lewis_spatial_join(
    centroids: dict[str, Centroid], plan_polygons: gpd.GeoDataFrame, district_col: str
) -> dict[str, int]:
    """Spatial-join block centroids against Lewis plan polygons."""
    import geopandas as gpd
    from shapely import Point

    geoids: list[str] = list(centroids.keys())
    points_gdf = gpd.GeoDataFrame(
        {"block_geoid": geoids},
        geometry=[Point(c.lon, c.lat) for c in centroids.values()],
        crs=plan_polygons.crs,
    )

    joined: gpd.GeoDataFrame = gpd.sjoin(
        points_gdf, plan_polygons, how="left", predicate="within"
    )
    joined = joined.drop_duplicates(subset="block_geoid", keep="first")

    has_match = joined[district_col].notna()
    matched = joined[has_match]

    assignements: dict[str, int] = dict(
        zip(matched["block_geoid"].astype(str), matched[district_col].astype(int))
    )

    return assignements
