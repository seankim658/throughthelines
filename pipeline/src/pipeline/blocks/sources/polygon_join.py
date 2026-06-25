"""Polygon-spatial-join block-assignment source.

Derives a block-to-district assignment by spatially joining block
centroids of the declared vintage against a plan's district polygons.
Covers any authority that publishes plan boundaries as polygons rather
than as a pre-computed block assignment file.
"""

from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path

from pipeline.config import BlockVintage
from pipeline.blocks.readers import load_plan_polygons
from pipeline.blocks.spatial_joins import plan_polygon_join
from pipeline.blocks.sources.base import BlockAssignmentSource, BlockGeometry
from pipeline.blocks.sources.provenance import PolygonJoinProvenance


@dataclass(frozen=True)
class PolygonJoinSource(BlockAssignmentSource):
    """A block-to-district assignment derived from plan polygons."""

    # --- Config ---
    geojson_path: Path
    source_file: str  # repo-relative path, mirrored in plan YAML
    _block_vintage: BlockVintage
    provider: str  # short label, e.g. "lewis"
    upstream_landing_url: str

    # Optional knobs; default matches Lewis's GeoJSON property naming
    district_property: str = "district"

    # --- Construction validation ---

    def __post_init__(self) -> None:
        if not self.geojson_path.exists():
            raise FileNotFoundError(
                f"polygon file not found at {self.geojson_path} "
                f"(provider={self.provider!r}); did you run `pipeline fetch`?"
            )

    # --- Contract ---

    @property
    def block_vintage(self) -> BlockVintage:
        return self._block_vintage

    def load(self, geometry: BlockGeometry) -> dict[str, int]:
        centroids = geometry.centroids(self._block_vintage)
        plan_polygons, district_col = load_plan_polygons(
            geojson_path=self.geojson_path, district_property=self.district_property
        )
        return plan_polygon_join(
            centroids=centroids, plan_polygons=plan_polygons, district_col=district_col
        )

    def provenance(self) -> PolygonJoinProvenance:
        return PolygonJoinProvenance(
            type="polygon_join",
            block_vintage=self._block_vintage,
            provider=self.provider,
            source_file=self.source_file,
            upstream_landing_url=self.upstream_landing_url,
        )
