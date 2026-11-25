"""Builders for the config files and project layout that tests load.

Each builder returns a TOML fragment, so a test assembles only the entries it
is about and loads them through the real config loaders.
"""

from __future__ import annotations

from pathlib import Path

from pipeline.config import ProjectPaths

BASE_SOURCES_TOML: str = """
schema_version = 1

[lewis]
repo = "JeffreyBLewis/congressional-district-boundaries"
commit_sha = "f107b1b6c149c1b759cbb9b5bb14111a2355d6a1"
landing_url = "https://github.com/JeffreyBLewis/congressional-district-boundaries"
homepage = "https://cdmaps.polisci.ucla.edu/"

[lewis.states.NC]
files = ["GeoJson/North Carolina_113_to_114.geojson"]

[voteview]
url = "https://voteview.com/static/data/out/members/HSall_members.csv"
landing_url = "https://voteview.com/data"

[census.tabblock.v2010]
url_template = "https://example.org/tl_2010_{fips}_tabblock10.zip"

[protomaps_basemap]
build_url = "https://build.protomaps.com/20260518.pmtiles"
landing_url = "https://maps.protomaps.com/builds"
max_zoom = 12
bbox = [-125.0, 24.3, -66.9, 49.4]

[providers.lewis]
name = "Jeffrey B. Lewis"

[providers.census]
name = "Census Bureau"

[providers.ncga]
name = "NC General Assembly"

[providers.tlc]
name = "Texas Legislative Council"
"""


def block_assignment_entry(state: str, congress: int, provider: str = "census") -> str:
    return f"""
[[block_assignment]]
provider = "{provider}"
state = "{state}"
congress = {congress}
vintage = "v2010"
url = "https://example.org/cd{congress}_{state.strip("*") or "national"}.zip"
landing_url = "https://example.org/bef"
inner_filename = "cd{congress}.txt"
district_column = "CD{congress}"
"""


def carry_entry(
    state: str, congress: int, same_as: int, extra: str = "", provider: str = "census"
) -> str:
    return f"""
[[block_assignment]]
provider = "{provider}"
state = "{state}"
congress = {congress}
same_as_congress = {same_as}
{extra}
"""


def geometry_entry(
    checksum: str,
    provider: str = "ncga",
    url: str = "https://example.org/ncga/plan.zip",
    state: str = "NC",
) -> str:
    return f"""
[[geometry_source]]
provider = "{provider}"
state = "{state}"
congress = 120
url = "{url}"
landing_url = "https://example.org/landing"
local_filename = "plan.zip"
checksum = "{checksum}"
source_crs = "EPSG:32119"
district_field = "DISTRICT"
"""


def write_sources(directory: Path, *entries: str) -> Path:
    path: Path = directory / "sources.toml"
    path.write_text(BASE_SOURCES_TOML + "".join(entries), encoding="utf-8")
    return path


def project_paths(root: Path) -> ProjectPaths:
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
