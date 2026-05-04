"""Loader for config/project.toml."""

from __future__ import annotations
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast
from importlib.metadata import version as _pkg_version, PackageNotFoundError

from pipeline.core import ChamberType, StateCode, SUPPORTED_CHAMBERS, SUPPORTED_STATES
from pipeline.config._common import (
    require_section,
    require_string,
    require_int,
    require_supported_schema_version,
)

SUPPORTED_SCHEMA_VERSIONS: frozenset[int] = frozenset({1})

# --- Errors ---


class ProjectConfigError(ValueError):
    """Raised when project.toml is missing required fields or malformed."""


# --- Models ---


@dataclass(frozen=True)
class ProjectSettings:

    name: str
    domain: str
    tagline: str
    repo_url: str


@dataclass(frozen=True)
class ScopeSettings:

    congress_start: int
    congress_end: int
    chambers: dict[StateCode, list[ChamberType]]


@dataclass(frozen=True)
class ProjectPaths:

    config_dir: Path
    request_filename: str
    sources_filename: str
    raw_dir: Path
    lewis_dir: Path
    voteview_dir: Path
    census_dir: Path
    tabblock_dir: Path
    bef_dir: Path
    manifest_dir: Path
    plans_dir: Path
    derived_dir: Path
    stitched_dir: Path
    members_file: Path
    block_lookup_dir: Path
    tiles_dir: Path
    plan_index_file: Path


@dataclass(frozen=True)
class ProjectConfig:

    schema_version: int
    project_settings: ProjectSettings
    project_paths: ProjectPaths
    scope: ScopeSettings

    @property
    def user_agent(self) -> str:
        slug = self.project_settings.name.lower().replace(" ", "-")
        try:
            v = _pkg_version("pipeline")
        except PackageNotFoundError:
            v = "unknown"
        return f"{slug}/{v} (+https://{self.project_settings.domain})"

    @property
    def request_config_path(self) -> Path:
        return self.project_paths.config_dir / Path(self.project_paths.request_filename)

    @property
    def sources_config_path(self) -> Path:
        return self.project_paths.config_dir / Path(self.project_paths.sources_filename)


# --- Loader ---


def load_project_config(path: Path, repo_root: str) -> ProjectConfig:
    """Load and validate project.toml."""

    with path.open("rb") as f:
        raw: dict[str, Any] = tomllib.load(f)

    schema_version: int = require_supported_schema_version(
        raw, SUPPORTED_SCHEMA_VERSIONS, path, ProjectConfigError
    )

    identity_raw: dict[str, Any] = require_section(
        raw, "project", path, ProjectConfigError
    )
    project_settings = ProjectSettings(
        name=require_string(identity_raw, "name", "project", path, ProjectConfigError),
        domain=require_string(
            identity_raw, "domain", "project", path, ProjectConfigError
        ),
        tagline=require_string(
            identity_raw, "tagline", "project", path, ProjectConfigError
        ),
        repo_url=require_string(
            identity_raw, "repo_url", "project", path, ProjectConfigError
        ),
    )

    paths_raw: dict[str, Any] = require_section(raw, "paths", path, ProjectConfigError)
    project_paths = ProjectPaths(
        config_dir=Path(
            require_string(
                paths_raw, "config_dir", "paths", path, ProjectConfigError
            ).format(repo_root=repo_root)
        ),
        request_filename=require_string(
            paths_raw, "request_filename", "paths", path, ProjectConfigError
        ),
        sources_filename=require_string(
            paths_raw, "sources_filename", "paths", path, ProjectConfigError
        ),
        raw_dir=Path(
            require_string(
                paths_raw, "raw_dir", "paths", path, ProjectConfigError
            ).format(repo_root=repo_root)
        ),
        lewis_dir=Path(
            require_string(
                paths_raw, "lewis_dir", "paths", path, ProjectConfigError
            ).format(repo_root=repo_root)
        ),
        voteview_dir=Path(
            require_string(
                paths_raw, "voteview_dir", "paths", path, ProjectConfigError
            ).format(repo_root=repo_root)
        ),
        census_dir=Path(
            require_string(
                paths_raw, "census_dir", "paths", path, ProjectConfigError
            ).format(repo_root=repo_root)
        ),
        tabblock_dir=Path(
            require_string(
                paths_raw, "tabblock_dir", "paths", path, ProjectConfigError
            ).format(repo_root=repo_root)
        ),
        bef_dir=Path(
            require_string(
                paths_raw, "bef_dir", "paths", path, ProjectConfigError
            ).format(repo_root=repo_root)
        ),
        manifest_dir=Path(
            require_string(
                paths_raw, "manifest_dir", "paths", path, ProjectConfigError
            ).format(repo_root=repo_root)
        ),
        plans_dir=Path(
            require_string(
                paths_raw, "plans_dir", "paths", path, ProjectConfigError
            ).format(repo_root=repo_root)
        ),
        derived_dir=Path(
            require_string(
                paths_raw, "derived_dir", "paths", path, ProjectConfigError
            ).format(repo_root=repo_root)
        ),
        stitched_dir=Path(
            require_string(
                paths_raw, "stitched_dir", "paths", path, ProjectConfigError
            ).format(repo_root=repo_root)
        ),
        members_file=Path(
            require_string(
                paths_raw, "members_file", "paths", path, ProjectConfigError
            ).format(repo_root=repo_root)
        ),
        block_lookup_dir=Path(
            require_string(
                paths_raw, "block_lookup_dir", "paths", path, ProjectConfigError
            ).format(repo_root=repo_root)
        ),
        tiles_dir=Path(
            require_string(
                paths_raw, "tiles_dir", "paths", path, ProjectConfigError
            ).format(repo_root=repo_root)
        ),
        plan_index_file=Path(
            require_string(
                paths_raw, "plan_index_file", "paths", path, ProjectConfigError
            ).format(repo_root=repo_root)
        ),
    )

    scope: ScopeSettings = _load_scope_section(raw, path)

    return ProjectConfig(
        schema_version=schema_version,
        project_settings=project_settings,
        project_paths=project_paths,
        scope=scope,
    )


def _load_scope_section(raw: dict[str, Any], path: Path) -> ScopeSettings:
    scope_raw: dict[str, Any] = require_section(raw, "scope", path, ProjectConfigError)

    congress_start: int = require_int(
        scope_raw, "congress_start", "scope", path, ProjectConfigError
    )
    congress_end: int = require_int(
        scope_raw, "congress_end", "scope", path, ProjectConfigError
    )

    if not (103 <= congress_start <= 130):
        raise ProjectConfigError(
            f"scope.congress_start ({congress_start}) must be between 103 "
            f"and 130 in {path}"
        )
    if not (103 <= congress_end <= 130):
        raise ProjectConfigError(
            f"scope.congress_end ({congress_end}) must be between 103 "
            f"and 130 in {path}"
        )

    chambers: dict[StateCode, list[ChamberType]] = _load_scope_chambers(scope_raw, path)

    return ScopeSettings(
        congress_start=congress_start, congress_end=congress_end, chambers=chambers
    )


def _load_scope_chambers(
    scope_raw: dict[str, Any], path: Path
) -> dict[StateCode, list[ChamberType]]:
    if "chambers" not in scope_raw:
        raise ProjectConfigError(f"missing [scope.chambers] section in {path}")
    chambers_raw = scope_raw["chambers"]
    if not isinstance(chambers_raw, dict):
        raise ProjectConfigError(f"[scope.chambers] must be a table in {path}")
    if not chambers_raw:
        raise ProjectConfigError(
            f"[scope.chambers] in {path} must contain at least one state"
        )

    chambers: dict[StateCode, list[ChamberType]] = {}
    for state_code, chamber_list in chambers_raw.items():
        if state_code not in SUPPORTED_STATES:
            supported_list: str = ", ".join(SUPPORTED_STATES)
            raise ProjectConfigError(
                f"unknown state code {state_code!r} in [scope.chambers] in "
                f"{path} (supported: {supported_list})"
            )
        if not isinstance(chamber_list, list) or not chamber_list:
            raise ProjectConfigError(
                f"[scope.chambers.{state_code}] must be a non-empty list in " f"{path}"
            )
        validated: list[ChamberType] = []
        for chamber in chamber_list:
            if chamber not in SUPPORTED_CHAMBERS:
                supported_chambers: str = ", ".join(SUPPORTED_CHAMBERS)
                raise ProjectConfigError(
                    f"unsupported chamber {chamber!r} for state {state_code} "
                    f"in [scope.chambers] in {path} "
                    f"(supported: {supported_chambers})"
                )
            validated.append(cast(ChamberType, chamber))
        chambers[cast(StateCode, state_code)] = validated

    return chambers
