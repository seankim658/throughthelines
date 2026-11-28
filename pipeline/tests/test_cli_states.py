from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
from config_fixtures import block_assignment_entry, write_sources

from pipeline.cli._common import CliError, load_sources_and_states
from pipeline.config import ProjectConfig, load_project_config
from pipeline.core import SupportedStateCode

_LEWIS_VA: str = """
[lewis.states.VA]
files = ["GeoJson/Virginia_113_to_117.geojson"]
"""


def _project(
    tmp_path: Path, repo_root: Path, built: list[SupportedStateCode]
) -> ProjectConfig:
    """Load the shipped project.toml rooted at `tmp_path`, building `built`."""
    config = load_project_config(
        repo_root / "config" / "project.toml", repo_root=str(tmp_path)
    )
    scope = replace(
        config.scope,
        chambers={state: ["congressional"] for state in built},
        planned=[],
        publish=[],
    )
    return replace(config, scope=scope)


def _write_sources(tmp_path: Path, *extra: str) -> None:
    config_dir: Path = tmp_path / "config"
    config_dir.mkdir()
    write_sources(config_dir, block_assignment_entry("*", 116), *extra)


def test_default_targets_are_the_built_states(tmp_path: Path, repo_root: Path) -> None:
    _write_sources(tmp_path, _LEWIS_VA)
    project = _project(tmp_path, repo_root, built=["NC"])

    _, target_states = load_sources_and_states(project, None)

    assert target_states == ["NC"]


def test_built_state_without_lewis_files_stops_the_step(
    tmp_path: Path, repo_root: Path
) -> None:
    _write_sources(tmp_path)
    project = _project(tmp_path, repo_root, built=["NC", "VA"])

    with pytest.raises(CliError, match=r"VA.*\[lewis\.states\]"):
        load_sources_and_states(project, None)


def test_state_option_must_name_a_built_state(tmp_path: Path, repo_root: Path) -> None:
    _write_sources(tmp_path, _LEWIS_VA)
    project = _project(tmp_path, repo_root, built=["NC"])

    with pytest.raises(CliError, match=r"\['VA'\] .*built"):
        load_sources_and_states(project, ["VA"])
