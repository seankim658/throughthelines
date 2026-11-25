from __future__ import annotations

from pathlib import Path

import pytest

from pipeline.config import FetchConfigError, load_fetch_config, load_project_config

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
"""


def _file_entry(state: str, congress: int) -> str:
    return f"""
[[block_assignment]]
provider = "census"
state = "{state}"
congress = {congress}
vintage = "v2010"
url = "https://example.org/cd{congress}_{state.strip("*") or "national"}.zip"
landing_url = "https://example.org/bef"
inner_filename = "cd{congress}.txt"
district_column = "CD{congress}"
"""


def _carry_entry(state: str, congress: int, same_as: int, extra: str = "") -> str:
    return f"""
[[block_assignment]]
provider = "census"
state = "{state}"
congress = {congress}
same_as_congress = {same_as}
{extra}
"""


def _write_sources(tmp_path: Path, *entries: str) -> Path:
    path: Path = tmp_path / "sources.toml"
    path.write_text(BASE_SOURCES_TOML + "".join(entries), encoding="utf-8")
    return path


def test_shipped_configs_load(repo_root: Path) -> None:
    config_dir: Path = repo_root / "config"

    fetch_config = load_fetch_config(config_dir / "sources.toml")
    project_config = load_project_config(
        config_dir / "project.toml", repo_root=str(repo_root)
    )

    assert fetch_config.block_assignments
    assert project_config.scope.chambers


def test_carry_to_real_entry_in_same_scope_loads(tmp_path: Path) -> None:
    path: Path = _write_sources(
        tmp_path, _file_entry("*", 116), _carry_entry("*", 117, 116)
    )

    config = load_fetch_config(path)

    assert [carry.same_as_congress for carry in config.block_carries] == [116]


def test_carry_cannot_target_another_scope(tmp_path: Path) -> None:
    path: Path = _write_sources(
        tmp_path, _file_entry("*", 116), _carry_entry("NC", 117, 116)
    )

    with pytest.raises(FetchConfigError, match="no source-owning"):
        load_fetch_config(path)


def test_carry_cannot_target_another_carry(tmp_path: Path) -> None:
    path: Path = _write_sources(
        tmp_path,
        _file_entry("*", 116),
        _carry_entry("*", 117, 116),
        _carry_entry("*", 118, 117),
    )

    with pytest.raises(FetchConfigError, match="same_as_congress=117"):
        load_fetch_config(path)


def test_carry_cannot_borrow_its_own_congress(tmp_path: Path) -> None:
    path: Path = _write_sources(
        tmp_path, _file_entry("*", 116), _carry_entry("*", 117, 117)
    )

    with pytest.raises(FetchConfigError, match="own congress"):
        load_fetch_config(path)


def test_carry_cannot_also_name_a_file(tmp_path: Path) -> None:
    path: Path = _write_sources(
        tmp_path,
        _file_entry("*", 116),
        _carry_entry("*", 117, 116, extra='url = "https://example.org/cd117.zip"'),
    )

    with pytest.raises(FetchConfigError, match="may not also set file field"):
        load_fetch_config(path)


def test_duplicate_entry_is_rejected(tmp_path: Path) -> None:
    path: Path = _write_sources(tmp_path, _file_entry("*", 116), _file_entry("*", 116))

    with pytest.raises(FetchConfigError, match="duplicate"):
        load_fetch_config(path)


def _geometry_entry(checksum: str) -> str:
    return f"""
[[geometry_source]]
provider = "ncga"
state = "NC"
congress = 120
url = "https://example.org/ncga/plan.zip"
landing_url = "https://example.org/landing"
local_filename = "plan.zip"
checksum = "{checksum}"
source_crs = "EPSG:32119"
district_field = "DISTRICT"
"""


@pytest.mark.parametrize(
    "checksum",
    [
        "c21e18d29a0f6dd52636c866ca3b05295a0757c6d6d98ee42ffa0b2eee795897",
        "md5:9e107d9d372bb6826bd81d3542a419d6",
        "sha256:c21e18d29a0f",
        "sha256:" + "g" * 64,
        "sha256:",
    ],
)
def test_malformed_checksum_pin_is_rejected(tmp_path: Path, checksum: str) -> None:
    path: Path = _write_sources(
        tmp_path, _file_entry("*", 116), _geometry_entry(checksum)
    )

    with pytest.raises(FetchConfigError, match="sha256:<64 hex digits>"):
        load_fetch_config(path)


def test_checksum_pin_hex_is_case_insensitive(tmp_path: Path) -> None:
    digest: str = "C21E18D29A0F6DD52636C866CA3B05295A0757C6D6D98EE42FFA0B2EEE795897"
    path: Path = _write_sources(
        tmp_path, _file_entry("*", 116), _geometry_entry(f"sha256:{digest}")
    )

    config = load_fetch_config(path)

    assert config.geometry_sources[0].sha256 == digest.lower()
