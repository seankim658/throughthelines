from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from pipeline.config import FetchConfig, ProjectPaths, load_fetch_config
from pipeline.fetch import FetchError, HttpResponse, fetch_state

NCGA_URL: str = "https://example.org/ncga/plan.zip"
NCGA_BODY: bytes = b"ncga plan shapefile"
OTHER_URL: str = "https://example.org/other/plan.zip"
OTHER_BODY: bytes = b"other plan shapefile"

SOURCES_TOML: str = """
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

[[block_assignment]]
provider = "census"
state = "*"
congress = 116
vintage = "v2010"
url = "https://example.org/cd116_national.zip"
landing_url = "https://example.org/bef"
inner_filename = "cd116.txt"
district_column = "CD116"
"""


class FakeDownloader:
    """Serve fixed bodies by URL, or report a URL as not modified."""

    def __init__(
        self, bodies: dict[str, bytes], not_modified: frozenset[str] = frozenset()
    ) -> None:
        self._bodies = bodies
        self._not_modified = not_modified

    def get(self, url: str, headers: dict[str, str]) -> HttpResponse:
        if url in self._not_modified:
            return HttpResponse(body=None, headers={})
        return HttpResponse(body=self._bodies.get(url, b"unpinned"), headers={})


def _geometry_entry(provider: str, url: str, checksum: str) -> str:
    return f"""
[[geometry_source]]
provider = "{provider}"
state = "NC"
congress = 120
url = "{url}"
landing_url = "https://example.org/landing"
local_filename = "plan.zip"
checksum = "{checksum}"
source_crs = "EPSG:32119"
district_field = "DISTRICT"
"""


def _pin(body: bytes) -> str:
    return f"sha256:{hashlib.sha256(body).hexdigest()}"


def _load_sources(tmp_path: Path, *entries: str) -> FetchConfig:
    path: Path = tmp_path / "sources.toml"
    path.write_text(SOURCES_TOML + "".join(entries), encoding="utf-8")
    return load_fetch_config(path)


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


def _geometry_path(paths: ProjectPaths, provider: str) -> Path:
    return paths.district_geometry_dir / provider / "NC" / "plan.zip"


def test_matching_checksum_saves_the_geometry_file(tmp_path: Path) -> None:
    sources = _load_sources(
        tmp_path, _geometry_entry("ncga", NCGA_URL, _pin(NCGA_BODY))
    )
    paths = _project_paths(tmp_path)

    result = fetch_state("NC", sources, paths, FakeDownloader({NCGA_URL: NCGA_BODY}))

    assert _geometry_path(paths, "ncga").read_bytes() == NCGA_BODY
    assert result.state_path.exists()


def test_checksum_mismatch_stops_the_fetch(tmp_path: Path) -> None:
    sources = _load_sources(
        tmp_path, _geometry_entry("ncga", NCGA_URL, _pin(b"curated version"))
    )
    paths = _project_paths(tmp_path)

    with pytest.raises(FetchError, match="checksum mismatch") as raised:
        fetch_state("NC", sources, paths, FakeDownloader({NCGA_URL: NCGA_BODY}))

    assert NCGA_URL in str(raised.value)
    assert hashlib.sha256(NCGA_BODY).hexdigest() in str(raised.value)


def test_mismatched_file_is_not_saved(tmp_path: Path) -> None:
    sources = _load_sources(
        tmp_path, _geometry_entry("ncga", NCGA_URL, _pin(b"curated version"))
    )
    paths = _project_paths(tmp_path)

    with pytest.raises(FetchError):
        fetch_state("NC", sources, paths, FakeDownloader({NCGA_URL: NCGA_BODY}))

    assert not _geometry_path(paths, "ncga").exists()
    assert not (paths.fetch_state_dir / "NC.yaml").exists()


def test_every_mismatch_is_reported_in_one_error(tmp_path: Path) -> None:
    sources = _load_sources(
        tmp_path,
        _geometry_entry("ncga", NCGA_URL, _pin(b"curated ncga")),
        _geometry_entry("other", OTHER_URL, _pin(b"curated other")),
    )
    paths = _project_paths(tmp_path)
    downloader = FakeDownloader({NCGA_URL: NCGA_BODY, OTHER_URL: OTHER_BODY})

    with pytest.raises(FetchError) as raised:
        fetch_state("NC", sources, paths, downloader)

    assert NCGA_URL in str(raised.value)
    assert OTHER_URL in str(raised.value)


def test_unchanged_local_file_is_checked_against_its_pin(tmp_path: Path) -> None:
    sources = _load_sources(
        tmp_path, _geometry_entry("ncga", NCGA_URL, _pin(b"curated version"))
    )
    paths = _project_paths(tmp_path)
    local: Path = _geometry_path(paths, "ncga")
    local.parent.mkdir(parents=True)
    local.write_bytes(NCGA_BODY)
    downloader = FakeDownloader({}, not_modified=frozenset({NCGA_URL}))

    with pytest.raises(FetchError, match="checksum mismatch"):
        fetch_state("NC", sources, paths, downloader)
