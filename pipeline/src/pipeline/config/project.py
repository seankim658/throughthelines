"""Loader for config/project.toml."""

from __future__ import annotations
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from importlib.metadata import version as _pkg_version, PackageNotFoundError

from pipeline.config._common import (
    require_section,
    require_string,
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
class ProjectPaths:

    config_dir: Path
    request_filename: str
    sources_filename: str
    raw_dir: Path
    lewis_dir: Path
    voteview_dir: Path
    manifest_file: Path
    plans_dir: Path
    derived_dir: Path
    stitched_dir: Path


@dataclass(frozen=True)
class ProjectConfig:

    schema_version: int
    project_settings: ProjectSettings
    project_paths: ProjectPaths

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
        manifest_file=Path(
            require_string(
                paths_raw, "manifest_file", "paths", path, ProjectConfigError
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
    )

    return ProjectConfig(
        schema_version=schema_version,
        project_settings=project_settings,
        project_paths=project_paths,
    )
