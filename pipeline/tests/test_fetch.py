from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from config_fixtures import (
    block_assignment_entry,
    geometry_entry,
    project_paths,
    write_sources,
)

from pipeline.config import FetchConfig, ProjectPaths, load_fetch_config
from pipeline.fetch import FetchError, HttpResponse, fetch_state

NCGA_URL: str = "https://example.org/ncga/plan.zip"
NCGA_BODY: bytes = b"ncga plan shapefile"
OTHER_URL: str = "https://example.org/tlc/plan.zip"
OTHER_BODY: bytes = b"other plan shapefile"


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


def _pin(body: bytes) -> str:
    return f"sha256:{hashlib.sha256(body).hexdigest()}"


def _load_sources(tmp_path: Path, *entries: str) -> FetchConfig:
    national: str = block_assignment_entry("*", 116)
    return load_fetch_config(write_sources(tmp_path, national, *entries))


def _geometry_path(paths: ProjectPaths, provider: str) -> Path:
    return paths.district_geometry_dir / provider / "NC" / "plan.zip"


def test_matching_checksum_saves_the_geometry_file(tmp_path: Path) -> None:
    sources = _load_sources(
        tmp_path, geometry_entry(_pin(NCGA_BODY), provider="ncga", url=NCGA_URL)
    )
    paths = project_paths(tmp_path)

    result = fetch_state("NC", sources, paths, FakeDownloader({NCGA_URL: NCGA_BODY}))

    assert _geometry_path(paths, "ncga").read_bytes() == NCGA_BODY
    assert result.state_path.exists()


def test_checksum_mismatch_stops_the_fetch(tmp_path: Path) -> None:
    sources = _load_sources(
        tmp_path,
        geometry_entry(_pin(b"curated version"), provider="ncga", url=NCGA_URL),
    )
    paths = project_paths(tmp_path)

    with pytest.raises(FetchError, match="checksum mismatch") as raised:
        fetch_state("NC", sources, paths, FakeDownloader({NCGA_URL: NCGA_BODY}))

    assert NCGA_URL in str(raised.value)
    assert hashlib.sha256(NCGA_BODY).hexdigest() in str(raised.value)


def test_mismatched_file_is_not_saved(tmp_path: Path) -> None:
    sources = _load_sources(
        tmp_path,
        geometry_entry(_pin(b"curated version"), provider="ncga", url=NCGA_URL),
    )
    paths = project_paths(tmp_path)

    with pytest.raises(FetchError):
        fetch_state("NC", sources, paths, FakeDownloader({NCGA_URL: NCGA_BODY}))

    assert not _geometry_path(paths, "ncga").exists()
    assert not (paths.fetch_state_dir / "NC.yaml").exists()


def test_every_mismatch_is_reported_in_one_error(tmp_path: Path) -> None:
    sources = _load_sources(
        tmp_path,
        geometry_entry(_pin(b"curated ncga"), provider="ncga", url=NCGA_URL),
        geometry_entry(_pin(b"curated tlc"), provider="tlc", url=OTHER_URL),
    )
    paths = project_paths(tmp_path)
    downloader = FakeDownloader({NCGA_URL: NCGA_BODY, OTHER_URL: OTHER_BODY})

    with pytest.raises(FetchError) as raised:
        fetch_state("NC", sources, paths, downloader)

    assert NCGA_URL in str(raised.value)
    assert OTHER_URL in str(raised.value)


def test_unchanged_local_file_is_checked_against_its_pin(tmp_path: Path) -> None:
    sources = _load_sources(
        tmp_path,
        geometry_entry(_pin(b"curated version"), provider="ncga", url=NCGA_URL),
    )
    paths = project_paths(tmp_path)
    local: Path = _geometry_path(paths, "ncga")
    local.parent.mkdir(parents=True)
    local.write_bytes(NCGA_BODY)
    downloader = FakeDownloader({}, not_modified=frozenset({NCGA_URL}))

    with pytest.raises(FetchError, match="checksum mismatch"):
        fetch_state("NC", sources, paths, downloader)
