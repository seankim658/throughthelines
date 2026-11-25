from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any

from config_fixtures import block_assignment_entry, geometry_entry, write_sources

from pipeline.config import (
    FetchConfig,
    ProjectConfig,
    load_fetch_config,
    load_project_config,
)
from pipeline.core import SupportedStateCode
from pipeline.manifest import build_manifest

UNPINNED: str = f"sha256:{'0' * 64}"


def _release(
    tmp_path: Path, repo_root: Path, states: list[SupportedStateCode]
) -> ProjectConfig:
    """Load the shipped project config, rooted in tmp_path, publishing `states`."""
    config = load_project_config(
        repo_root / "config" / "project.toml", repo_root=str(tmp_path)
    )
    scope = replace(
        config.scope,
        chambers={state: ["congressional"] for state in states},
        publish=list(states),
    )
    return replace(config, scope=scope)


def _write_derived(config: ProjectConfig) -> None:
    """Write stand-ins for every artifact the manifest references."""
    paths = config.project_paths
    scope = config.scope
    for global_path in (paths.plan_index_file, paths.members_file, paths.basemap_file):
        global_path.parent.mkdir(parents=True, exist_ok=True)
        global_path.write_bytes(b"{}")
    for state in scope.chambers:
        tiles: Path = paths.tiles_dir / f"{state}_congressional.pmtiles"
        tiles.parent.mkdir(parents=True, exist_ok=True)
        tiles.write_bytes(b"tiles")
        lookup: Path = (
            paths.block_lookup_dir / f"block_lookup_{state}_congressional.json"
        )
        lookup.parent.mkdir(parents=True, exist_ok=True)
        lookup.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "congress_start": scope.congress_start,
                    "congress_end": scope.congress_end,
                    "congresses": [],
                }
            ),
            encoding="utf-8",
        )


def _manifest_providers(config: ProjectConfig, sources: FetchConfig) -> dict[str, Any]:
    _write_derived(config)
    path: Path = config.project_paths.manifest_file
    build_manifest(config, sources, path)
    manifest: dict[str, Any] = json.loads(path.read_text("utf-8"))
    providers: dict[str, Any] = manifest["sources"]["providers"]
    return providers


def test_manifest_names_every_provider_a_published_state_uses(
    tmp_path: Path, repo_root: Path
) -> None:
    sources = load_fetch_config(
        write_sources(
            tmp_path, block_assignment_entry("*", 116), geometry_entry(UNPINNED)
        )
    )

    providers = _manifest_providers(_release(tmp_path, repo_root, ["NC"]), sources)

    assert providers == {
        "lewis": {"name": "Jeffrey B. Lewis"},
        "census": {"name": "Census Bureau"},
        "ncga": {"name": "NC General Assembly"},
    }


def test_manifest_leaves_out_providers_only_unpublished_states_use(
    tmp_path: Path, repo_root: Path
) -> None:
    texas: str = geometry_entry(
        UNPINNED, provider="tlc", url="https://example.org/tlc.zip", state="TX"
    )
    sources = load_fetch_config(
        write_sources(tmp_path, block_assignment_entry("*", 116), texas)
    )

    providers = _manifest_providers(_release(tmp_path, repo_root, ["NC"]), sources)

    assert "tlc" not in providers
