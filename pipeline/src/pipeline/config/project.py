"""Loader for config/project.toml."""

from __future__ import annotations
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast
from importlib.metadata import version as _pkg_version, PackageNotFoundError

from pipeline.core import (
    SupportedChamberType,
    SupportedStateCode,
    SUPPORTED_CHAMBERS,
    SUPPORTED_STATES,
    ALL_US_STATE_CODES,
)
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
    chambers: dict[SupportedStateCode, list[SupportedChamberType]]
    planned: list[str]


@dataclass(frozen=True)
class ProjectPaths:

    config_dir: Path
    request_filename: str
    sources_filename: str
    raw_dir: Path
    district_geometry_dir: Path
    lewis_dir: Path
    voteview_dir: Path
    census_dir: Path
    tabblock_dir: Path
    bef_dir: Path
    fetch_state_dir: Path
    plans_dir: Path
    derived_dir: Path
    stitched_dir: Path
    members_file: Path
    block_lookup_dir: Path
    tiles_dir: Path
    basemap_file: Path
    plan_index_file: Path
    manifest_file: Path


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


# --- Helpers ---


def _require_path(resolved_paths: dict[str, Any], key: str, path: Path) -> Path:
    value = resolved_paths.get(key)
    if not value:
        raise ProjectConfigError(f"missing or invalid paths.{key} in {path}")
    return Path(value)


def _resolve_paths(
    paths_raw: dict[str, Any], repo_root: str, path: Path
) -> dict[str, str]:
    """Resolve {placeholder} references in the [paths] table."""
    resolved: dict[str, str] = {"repo_root": repo_root}
    pending: dict[str, str] = {
        key: value for key, value in paths_raw.items() if isinstance(value, str)
    }

    while pending:
        progressed: bool = False
        for key in list(pending):
            try:
                resolved[key] = pending[key].format(**resolved)
            except KeyError:
                continue
            del pending[key]
            progressed = True
        if not progressed:
            break

    if pending:
        unresolved = ", ".join(sorted(pending))
        raise ProjectConfigError(
            f"unresolved or cyclic path reference(s) in [paths] in "
            f"{path}: {unresolved}"
        )

    del resolved["repo_root"]
    return resolved


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
    resolved_paths = _resolve_paths(paths_raw, repo_root, path)
    project_paths = ProjectPaths(
        config_dir=_require_path(resolved_paths, "config_dir", path),
        request_filename=require_string(
            paths_raw, "request_filename", "paths", path, ProjectConfigError
        ),
        sources_filename=require_string(
            paths_raw, "sources_filename", "paths", path, ProjectConfigError
        ),
        raw_dir=_require_path(resolved_paths, "raw_dir", path),
        district_geometry_dir=_require_path(
            resolved_paths, "district_geometry_dir", path
        ),
        lewis_dir=_require_path(resolved_paths, "lewis_dir", path),
        voteview_dir=_require_path(resolved_paths, "voteview_dir", path),
        census_dir=_require_path(resolved_paths, "census_dir", path),
        tabblock_dir=_require_path(resolved_paths, "tabblock_dir", path),
        bef_dir=_require_path(resolved_paths, "bef_dir", path),
        fetch_state_dir=_require_path(resolved_paths, "fetch_state_dir", path),
        plans_dir=_require_path(resolved_paths, "plans_dir", path),
        derived_dir=_require_path(resolved_paths, "derived_dir", path),
        stitched_dir=_require_path(resolved_paths, "stitched_dir", path),
        members_file=_require_path(resolved_paths, "members_file", path),
        block_lookup_dir=_require_path(resolved_paths, "block_lookup_dir", path),
        tiles_dir=_require_path(resolved_paths, "tiles_dir", path),
        basemap_file=_require_path(resolved_paths, "basemap_file", path),
        plan_index_file=_require_path(resolved_paths, "plan_index_file", path),
        manifest_file=_require_path(resolved_paths, "manifest_file", path),
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

    chambers: dict[SupportedStateCode, list[SupportedChamberType]] = (
        _load_scope_chambers(scope_raw, path)
    )
    planned: list[str] = _load_scope_planned(scope_raw, chambers, path)

    return ScopeSettings(
        congress_start=congress_start,
        congress_end=congress_end,
        chambers=chambers,
        planned=planned,
    )


def _load_scope_chambers(
    scope_raw: dict[str, Any], path: Path
) -> dict[SupportedStateCode, list[SupportedChamberType]]:
    if "chambers" not in scope_raw:
        raise ProjectConfigError(f"missing [scope.chambers] section in {path}")
    chambers_raw = scope_raw["chambers"]
    if not isinstance(chambers_raw, dict):
        raise ProjectConfigError(f"[scope.chambers] must be a table in {path}")
    if not chambers_raw:
        raise ProjectConfigError(
            f"[scope.chambers] in {path} must contain at least one state"
        )

    chambers: dict[SupportedStateCode, list[SupportedChamberType]] = {}
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
        validated: list[SupportedChamberType] = []
        for chamber in chamber_list:
            if chamber not in SUPPORTED_CHAMBERS:
                supported_chambers: str = ", ".join(SUPPORTED_CHAMBERS)
                raise ProjectConfigError(
                    f"unsupported chamber {chamber!r} for state {state_code} "
                    f"in [scope.chambers] in {path} "
                    f"(supported: {supported_chambers})"
                )
            validated.append(cast(SupportedChamberType, chamber))
        chambers[cast(SupportedStateCode, state_code)] = validated

    return chambers


def _load_scope_planned(
    scope_raw: dict[str, Any],
    chambers: dict[SupportedStateCode, list[SupportedChamberType]],
    path: Path,
) -> list[str]:
    planned_raw: Any = scope_raw.get("planned", [])
    if not isinstance(planned_raw, list):
        raise ProjectConfigError(f"scope.planned must be a list in {path}")

    planned: list[str] = []
    for entry in planned_raw:
        if not isinstance(entry, str) or entry not in ALL_US_STATE_CODES:
            raise ProjectConfigError(
                f"unknown state code {entry!r} in scope.planned in "
                f"{path} (expected a valid US state code)"
            )
        if entry in chambers:
            raise ProjectConfigError(
                f"state {entry!r} cannot appear in both scope.planned and "
                f"scope.chambers in {path}"
            )
        planned.append(entry)
    return planned
