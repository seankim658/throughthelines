from __future__ import annotations

from pathlib import Path

import pytest
from config_fixtures import (
    block_assignment_entry,
    carry_entry,
    geometry_entry,
    write_sources,
)

from pipeline.config import (
    LEWIS_PROVIDER,
    FetchConfigError,
    load_fetch_config,
    load_project_config,
)


def test_shipped_configs_load(repo_root: Path) -> None:
    config_dir: Path = repo_root / "config"

    fetch_config = load_fetch_config(config_dir / "sources.toml")
    project_config = load_project_config(
        config_dir / "project.toml", repo_root=str(repo_root)
    )

    assert fetch_config.block_assignments
    assert project_config.scope.chambers


def test_carry_to_real_entry_in_same_scope_loads(tmp_path: Path) -> None:
    path: Path = write_sources(
        tmp_path, block_assignment_entry("*", 116), carry_entry("*", 117, 116)
    )

    config = load_fetch_config(path)

    assert [carry.same_as_congress for carry in config.block_carries] == [116]


def test_carry_cannot_target_another_scope(tmp_path: Path) -> None:
    path: Path = write_sources(
        tmp_path, block_assignment_entry("*", 116), carry_entry("NC", 117, 116)
    )

    with pytest.raises(FetchConfigError, match="no source-owning"):
        load_fetch_config(path)


def test_carry_cannot_target_another_carry(tmp_path: Path) -> None:
    path: Path = write_sources(
        tmp_path,
        block_assignment_entry("*", 116),
        carry_entry("*", 117, 116),
        carry_entry("*", 118, 117),
    )

    with pytest.raises(FetchConfigError, match="same_as_congress=117"):
        load_fetch_config(path)


def test_carry_cannot_borrow_its_own_congress(tmp_path: Path) -> None:
    path: Path = write_sources(
        tmp_path, block_assignment_entry("*", 116), carry_entry("*", 117, 117)
    )

    with pytest.raises(FetchConfigError, match="own congress"):
        load_fetch_config(path)


def test_carry_cannot_also_name_a_file(tmp_path: Path) -> None:
    path: Path = write_sources(
        tmp_path,
        block_assignment_entry("*", 116),
        carry_entry("*", 117, 116, extra='url = "https://example.org/cd117.zip"'),
    )

    with pytest.raises(FetchConfigError, match="may not also set file field"):
        load_fetch_config(path)


def test_duplicate_entry_is_rejected(tmp_path: Path) -> None:
    path: Path = write_sources(
        tmp_path, block_assignment_entry("*", 116), block_assignment_entry("*", 116)
    )

    with pytest.raises(FetchConfigError, match="duplicate"):
        load_fetch_config(path)


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
    path: Path = write_sources(
        tmp_path, block_assignment_entry("*", 116), geometry_entry(checksum)
    )

    with pytest.raises(FetchConfigError, match="sha256:<64 hex digits>"):
        load_fetch_config(path)


def test_checksum_pin_hex_is_case_insensitive(tmp_path: Path) -> None:
    digest: str = "C21E18D29A0F6DD52636C866CA3B05295A0757C6D6D98EE42FFA0B2EEE795897"
    path: Path = write_sources(
        tmp_path, block_assignment_entry("*", 116), geometry_entry(f"sha256:{digest}")
    )

    config = load_fetch_config(path)

    assert config.geometry_sources[0].sha256 == digest.lower()


def test_provider_names_load(tmp_path: Path) -> None:
    path: Path = write_sources(tmp_path, block_assignment_entry("*", 116))

    config = load_fetch_config(path)

    assert config.provider_names["census"] == "Census Bureau"
    assert config.provider_names[LEWIS_PROVIDER] == "Jeffrey B. Lewis"


@pytest.mark.parametrize(
    "entry",
    [
        geometry_entry(f"sha256:{'0' * 64}", provider="nyc"),
        block_assignment_entry("NC", 117, provider="nyc"),
        carry_entry("NC", 117, 116, provider="nyc"),
    ],
    ids=["geometry_source", "block_assignment_file", "block_assignment_carry"],
)
def test_entry_naming_an_unregistered_provider_is_rejected(
    tmp_path: Path, entry: str
) -> None:
    path: Path = write_sources(
        tmp_path, block_assignment_entry("NC", 116, provider="nyc"), entry
    )

    with pytest.raises(FetchConfigError, match=r"provider 'nyc' .* \[providers\]"):
        load_fetch_config(path)


def test_lewis_provider_must_be_registered(tmp_path: Path) -> None:
    path: Path = write_sources(tmp_path, block_assignment_entry("*", 116))
    path.write_text(
        path.read_text("utf-8").replace(
            '[providers.lewis]\nname = "Jeffrey B. Lewis"\n', ""
        ),
        encoding="utf-8",
    )

    with pytest.raises(FetchConfigError, match=r"provider 'lewis' .* \[providers\]"):
        load_fetch_config(path)


def test_blank_provider_name_is_rejected(tmp_path: Path) -> None:
    path: Path = write_sources(tmp_path, block_assignment_entry("*", 116))
    path.write_text(
        path.read_text("utf-8").replace('name = "Census Bureau"', 'name = "  "'),
        encoding="utf-8",
    )

    with pytest.raises(FetchConfigError, match=r"providers\.census\.name"):
        load_fetch_config(path)
