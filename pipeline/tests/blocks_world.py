"""A tiny synthetic state for block-lookup build tests.

The state is four one-degree blocks in a row. Every Census decade uses the
same squares under its own GEOIDs, so the cross-decade joins link block i to
block i. Each assignment source splits the blocks into districts differently,
so a block's history shows which source filled each Congress.
"""

from __future__ import annotations

import csv
import io
import json
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import geopandas as gpd
from shapely.geometry import Polygon, box

from pipeline.blocks import BlocksBuildResult, build_blocks
from pipeline.config import (
    BlockAssignmentCarry,
    BlockAssignmentEntry,
    BlockVintage,
    CensusSource,
    ProjectPaths,
    ScopeSettings,
)
from pipeline.core import SupportedStateCode
from pipeline.plans import Plan

STATE_FIPS: str = "37"
BLOCK_COUNT: int = 4
CONGRESS_START: int = 112
CONGRESS_END: int = 115
LEWIS_LANDING_URL: str = "https://example.org/lewis"

# Districts per block index, one split per source. The polygon split matches
# the plan GeoJSON that _write_plan_polygons draws.
POLYGON_SPLIT: tuple[int, ...] = (1, 1, 2, 2)
NATIONAL_113_SPLIT: tuple[int, ...] = (1, 1, 1, 2)
STATE_115_SPLIT: tuple[int, ...] = (1, 2, 2, 2)

_TABBLOCK_COLUMNS: dict[BlockVintage, tuple[str, str, str]] = {
    "v2020": ("GEOID20", "INTPTLON20", "INTPTLAT20"),
    "v2010": ("GEOID10", "INTPTLON10", "INTPTLAT10"),
    "v2000": ("BLKIDFP00", "INTPTLON00", "INTPTLAT00"),
}
_GEOID_TRACT: dict[BlockVintage, str] = {
    "v2020": "001000100",
    "v2010": "001000200",
    "v2000": "001000300",
}
_POLYGON_SOURCE_FILE: str = "district_geometry/lewis/NC/plan_112.geojson"
_BEF_LANDING_URL: str = "https://example.org/bef"


def block_geoid(vintage: BlockVintage, index: int) -> str:
    """Return the 15-digit GEOID of block `index` in `vintage`."""
    return f"{STATE_FIPS}{_GEOID_TRACT[vintage]}{index:04d}"


@dataclass
class BlockWorld:
    """Inputs for one `build_blocks` call, written under a temp folder."""

    root: Path
    paths: ProjectPaths
    census: CensusSource
    plans: list[Plan]
    assignments: list[BlockAssignmentEntry] = field(default_factory=list)
    carries: list[BlockAssignmentCarry] = field(default_factory=list)
    congress_start: int = CONGRESS_START
    congress_end: int = CONGRESS_END

    @property
    def output_path(self) -> Path:
        return self.paths.block_lookup_dir / "block_lookup_NC_congressional.json"

    def build(
        self, *, allow_missing: bool = False, spatial_join_fallback: bool = False
    ) -> BlocksBuildResult:
        return build_blocks(
            plans=self.plans,
            state="NC",
            chamber="congressional",
            scope=ScopeSettings(
                congress_start=self.congress_start,
                congress_end=self.congress_end,
                chambers={"NC": ["congressional"]},
                planned=[],
                publish=["NC"],
            ),
            project_paths=self.paths,
            census_source=self.census,
            block_assignments=self.assignments,
            block_carries=self.carries,
            geometry_sources=[],
            lewis_landing_url=LEWIS_LANDING_URL,
            output_path=self.output_path,
            allow_missing=allow_missing,
            spatial_join_fallback=spatial_join_fallback,
        )

    def output(self) -> dict[str, Any]:
        loaded: dict[str, Any] = json.loads(self.output_path.read_text("utf-8"))
        return loaded

    def history_of(self, index: int) -> list[int | None]:
        """Return the district history of 2020 block `index`."""
        output: dict[str, Any] = self.output()
        history_index: int = output["blocks"][block_geoid("v2020", index)]
        history: list[int | None] = output["histories"][history_index]
        return history

    def add_plan(self, plan_id: str, start: int, end: int | None) -> Plan:
        """Write polygons for a new plan over [start, end] and return it.

        The polygons use the same split as the default plan.
        """
        source_file: str = f"district_geometry/lewis/NC/{plan_id}.geojson"
        _write_plan_polygons(self.paths.raw_dir / source_file)
        return _plan(plan_id, start, end, source_file)

    def write_bef(
        self,
        *,
        state: SupportedStateCode | Literal["*"],
        congress: int,
        split: tuple[int, ...],
    ) -> BlockAssignmentEntry:
        """Write a 2010-vintage assignment zip and return its config entry."""
        inner_filename: str = f"cd{congress}.txt"
        url: str = (
            f"https://example.org/{state.strip('*') or 'national'}_cd{congress}.zip"
        )
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(["BLOCKID", f"CD{congress}"])
        for index, district in enumerate(split):
            writer.writerow([block_geoid("v2010", index), district])
        self.paths.bef_dir.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(self.paths.bef_dir / Path(url).name, "w") as archive:
            archive.writestr(inner_filename, buffer.getvalue())
        return BlockAssignmentEntry(
            provider="census" if state == "*" else "ncga",
            state=state,
            congress=congress,
            vintage="v2010",
            url=url,
            landing_url=_BEF_LANDING_URL,
            inner_filename=inner_filename,
            district_column=f"CD{congress}",
        )


def make_block_world(root: Path) -> BlockWorld:
    """Write the default world, which exercises every resolution path.

    112 joins polygons (pre-BEF), 113 has a national file, 114 carries 113
    nationally, and 115 has both a national carry and a state file.
    """
    paths: ProjectPaths = _project_paths(root)
    census: CensusSource = _write_tabblocks(paths)
    _write_plan_polygons(paths.raw_dir / _POLYGON_SOURCE_FILE)
    world = BlockWorld(
        root=root,
        paths=paths,
        census=census,
        plans=[
            _plan("NC_112_2011", 112, 112, _POLYGON_SOURCE_FILE),
            _plan(
                "NC_113_2013", 113, 115, "district_geometry/lewis/NC/plan_113.geojson"
            ),
        ],
    )
    world.assignments = [
        world.write_bef(state="*", congress=113, split=NATIONAL_113_SPLIT),
        world.write_bef(state="NC", congress=115, split=STATE_115_SPLIT),
    ]
    world.carries = [
        BlockAssignmentCarry(
            provider="census", state="*", congress=114, same_as_congress=113
        ),
        BlockAssignmentCarry(
            provider="census", state="*", congress=115, same_as_congress=113
        ),
    ]
    return world


def _project_paths(root: Path) -> ProjectPaths:
    raw: Path = root / "raw"
    derived: Path = root / "derived"
    return ProjectPaths(
        config_dir=root / "config",
        request_filename="request.toml",
        sources_filename="sources.toml",
        raw_dir=raw,
        district_geometry_dir=raw / "district_geometry",
        lewis_dir=raw / "district_geometry" / "lewis",
        voteview_dir=raw / "voteview",
        census_dir=raw / "census",
        tabblock_dir=raw / "census" / "tabblock",
        bef_dir=raw / "census" / "bef",
        fetch_state_dir=raw / "fetch_state",
        plans_dir=root / "plans",
        derived_dir=derived,
        stitched_dir=derived / "stitched",
        members_file=derived / "members.json",
        block_lookup_dir=derived / "block_lookup",
        tiles_dir=derived / "tiles",
        basemap_file=derived / "basemap.pmtiles",
        plan_index_file=derived / "plan_index.json",
        manifest_file=derived / "manifest.json",
    )


def _write_tabblocks(paths: ProjectPaths) -> CensusSource:
    templates: dict[BlockVintage, str] = {}
    for vintage, (geoid_col, lon_col, lat_col) in _TABBLOCK_COLUMNS.items():
        year: str = vintage[1:]
        templates[vintage] = f"https://example.org/tl_{year}_{{fips}}_tabblock.zip"
        frame = gpd.GeoDataFrame(
            {
                geoid_col: [block_geoid(vintage, i) for i in range(BLOCK_COUNT)],
                lon_col: [f"{i + 0.5:+.7f}" for i in range(BLOCK_COUNT)],
                lat_col: ["+0.5000000"] * BLOCK_COUNT,
            },
            geometry=[box(i, 0, i + 1, 1) for i in range(BLOCK_COUNT)],
            crs="EPSG:4269",
        )
        zip_path: Path = (
            paths.tabblock_dir / year / "NC" / f"tl_{year}_{STATE_FIPS}_tabblock.zip"
        )
        _write_zipped_shapefile(frame, zip_path)
    return CensusSource(tabblock_templates=templates)


def _write_zipped_shapefile(frame: gpd.GeoDataFrame, zip_path: Path) -> None:
    shapefile_dir: Path = zip_path.parent / f"{zip_path.stem}_shp"
    shapefile_dir.mkdir(parents=True, exist_ok=True)
    frame.to_file(shapefile_dir / f"{zip_path.stem}.shp")
    with zipfile.ZipFile(zip_path, "w") as archive:
        for component in sorted(shapefile_dir.iterdir()):
            archive.write(component, arcname=component.name)


def _write_plan_polygons(path: Path) -> None:
    # District 1 covers blocks 0 and 1, district 2 covers blocks 2 and 3.
    write_district_polygons(path, {1: box(0, 0, 2, 1), 2: box(2, 0, 4, 1)})


def write_district_polygons(path: Path, districts: dict[int, Polygon]) -> None:
    """Write a plan GeoJSON with one polygon per district number."""
    frame = gpd.GeoDataFrame(
        {"district": list(districts)},
        geometry=list(districts.values()),
        crs="EPSG:4269",
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_file(path, driver="GeoJSON")


def _plan(plan_id: str, start: int, end: int | None, source_file: str) -> Plan:
    return Plan.model_validate(
        {
            "plan_id": plan_id,
            "state": "NC",
            "chamber": "congressional",
            "congress_start": start,
            "congress_end": end,
            "source_file": source_file,
            "source_commit": "0" * 40,
            "schema_version": 1,
        }
    )
