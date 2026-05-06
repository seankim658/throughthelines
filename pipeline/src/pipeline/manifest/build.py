"""Build the manifest.json, the frontend's dicsovery document.

Every artifact's URL, size, integrity hash, and provenance is
reachable by the frontend through the manifest file. The frontend
fetches the manifest on every page load an resolves any subsequent
artifact URL through `build.url_prefix` and `artifacts[*].path`.

This also serves as a build-time integrity gate: every artifact named
in the manifest must exist on disk before the manifest is emitted. A
missing artifact aborts the build rather than producing downstream 404s.
"""

from __future__ import annotations
import hashlib
import json
import os
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pipeline.config import ProjectConfig
from pipeline.core import STATE_INFO, ChamberType, StateCode, write_json_atomic

_OUTPUT_SCHEMA_VERSION: int = 1

# Streaming hash chunk size
_HASH_CHUNK_BYTES: int = 64 * 1024

# Block-lookup output schema versions this builder accepts. The block-lookup pipeline
# emits per-Congress provenance under a `congresses` field which gets propagated into
# the manifest. If the on-disk block-lookup file has a schema_version below this floor,
# the file must be regenerated.
_MIN_BLOCK_LOOKUP_SCHEMA_VERSION: int = 1

# Ceiling on `git rev-parse HEAD`
_GIT_SUBPROCESSES_TIMEOUT_SECONDS: float = 2.0

_GIT_SHA_ENV_VAR: str = "THROUGH_THE_LINES_GIT_SHA"

# --- Errors ---


class ManifestBuildError(Exception):
    """Raised when the manifest build cannot complete."""


# --- Models ---


@dataclass(frozen=True)
class ManifestBuildResult:

    output_path: Path
    git_sha: str | None
    built_at: str
    url_prefix: str | None
    states_count: int
    chambers_count: int
    total_artifacts: int
    warnings: list[str] = field(default_factory=list)


# --- API ---


def build_manifest(
    project_config: ProjectConfig, output_path: Path
) -> ManifestBuildResult:
    """Assemble manifest.json from the existing derived artifacts.

    Run as the last step in the build sequence. Verifies every referenced
    artifact exists on disk.
    """
    paths = project_config.project_paths
    derived_dir: Path = paths.derived_dir
    scope = project_config.scope

    warnings: list[str] = []

    git_sha: str | None = _resolve_git_sha(warnings)
    built_at: str = _now_utc_iso8601()
    url_prefix: str | None = _compute_url_prefix(git_sha)

    global_artifacts: dict[str, dict[str, Any]] = {
        "plan_index": _artifact_ref(paths.plan_index_file, derived_dir, "plan-index"),
        "members": _artifact_ref(paths.members_file, derived_dir, "members"),
    }

    states_section: dict[str, dict[str, Any]] = {}
    chambers_count: int = 0
    artifacts_count: int = len(global_artifacts)

    for state in sorted(scope.chambers.keys()):
        state_section, state_artifact_count, state_chamber_count = (
            _assemble_state_section(state, project_config)
        )
        states_section[state] = state_section
        chambers_count += state_chamber_count
        artifacts_count += state_artifact_count

    manifest: dict[str, Any] = {
        "schema_version": _OUTPUT_SCHEMA_VERSION,
        "build": {
            "git_sha": git_sha,
            "built_at": built_at,
            "url_prefix": url_prefix,
        },
        "scope": {
            "congress_start": scope.congress_start,
            "congress_end": scope.congress_end,
        },
        "artifacts": global_artifacts,
        "states": states_section,
    }

    write_json_atomic(output_path, manifest)

    return ManifestBuildResult(
        output_path=output_path,
        git_sha=git_sha,
        built_at=built_at,
        url_prefix=url_prefix,
        states_count=len(states_section),
        chambers_count=chambers_count,
        total_artifacts=artifacts_count,
        warnings=warnings,
    )


# --- Build Identity ---


def _resolve_git_sha(warnings: list[str]) -> str | None:
    """Resolve the git SHA the pipeline ran from.

    Resolution order:
        1. THROUGH_THE_LINES_GIT_SHA env var (CI runners with detached HEAD)
        2. `git rev-parse HEAD` from the working directory
        3. None
    """
    env_sha: str | None = os.environ.get(_GIT_SHA_ENV_VAR)
    if env_sha:
        return env_sha.strip()

    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            timeout=_GIT_SUBPROCESSES_TIMEOUT_SECONDS,
        )
    except (
        subprocess.CalledProcessError,
        FileNotFoundError,
        subprocess.TimeoutExpired,
    ):
        warnings.append(
            "git_sha resolved to null; manifest will emit with null url_prefix "
            f"(set {_GIT_SHA_ENV_VAR} or run inside a git checkout to populate)"
        )
        return None

    sha: str = result.stdout.strip()
    return sha if sha else None


def _compute_url_prefix(git_sha: str | None) -> str | None:
    """Compute the versioned URL prefix from a git SHA.

    Returns `v/{git_sha}` or None when no SHA is available. The
    frontend joins this onto every artifact path at runtime. A
    None prefix means the fontend falls back to flat paths under
    the bucket root.
    """
    if git_sha is None:
        return None
    return f"v/{git_sha}"


def _now_utc_iso8601() -> str:
    """Build identity timestamp in `YYYY-MM-DDTHH:MM:SSZ` form."""
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


# --- Artifact Assembly ---


def _hash_file(path: Path) -> str:
    """Return the streaming SHA-256 hex digest of a file's bytes."""
    hasher = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk: bytes = f.read(_HASH_CHUNK_BYTES)
            if not chunk:
                break
            hasher.update(chunk)
    return hasher.hexdigest()


def _artifact_ref(
    artifact_path: Path, derived_dir: Path, producing_step: str
) -> dict[str, Any]:
    """Build an ArtifactRef dict for one on-disk artifact."""
    if not artifact_path.exists():
        raise ManifestBuildError(
            f"required artifact missing at {artifact_path} "
            f"(did you run `pipeline {producing_step}`?)"
        )

    relative_path: Path = artifact_path.relative_to(derived_dir)
    return {
        "path": relative_path.as_posix(),
        "size_bytes": artifact_path.stat().st_size,
        "sha256": _hash_file(artifact_path),
    }


# --- Per-state Assembly ---


def _assemble_state_section(
    state: StateCode, project_config: ProjectConfig
) -> tuple[dict[str, Any], int, int]:
    """Build one `states.{STATE}` section.

    Returns the section dict, the count of artifacts referenced from it,
    and the count of chambers covered.
    """
    paths = project_config.project_paths
    derived_dir: Path = paths.derived_dir
    scope = project_config.scope
    state_info = STATE_INFO[state]

    chambers: list[ChamberType] = scope.chambers[state]
    chambers_section: dict[str, dict[str, Any]] = {}
    artifacts_count: int = 0

    for chamber in chambers:
        block_lookup_path: Path = (
            paths.block_lookup_dir / f"block_lookup_{state}_{chamber}.json"
        )
        tiles_path: Path = paths.tiles_dir / f"{state}_{chamber}.pmtiles"

        chamber_artifacts: dict[str, dict[str, Any]] = {
            "block_lookup": _artifact_ref(block_lookup_path, derived_dir, "blocks"),
            "tiles": _artifact_ref(tiles_path, derived_dir, "tiles"),
        }
        artifacts_count += len(chamber_artifacts)

        congresses_payload: list[dict[str, Any]] = _load_block_lookup_congresses(
            block_lookup_path,
            expected_congress_start=scope.congress_start,
            expected_congress_end=scope.congress_end,
        )

        chambers_section[chamber] = {
            "artifacts": chamber_artifacts,
            "congresses": congresses_payload,
        }

    state_section: dict[str, Any] = {
        "code": state_info.code,
        "name": state_info.display_name,
        "fips": state_info.fips,
        "chambers": chambers_section,
    }

    return state_section, artifacts_count, len(chambers)


def _load_block_lookup_congresses(
    block_lookup_path: Path,
    expected_congress_start: int,
    expected_congress_end: int,
) -> list[dict[str, Any]]:
    """Read the per-Congress provenance from a block-lookup file."""
    try:
        with block_lookup_path.open("rb") as f:
            payload: Any = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        raise ManifestBuildError(
            f"failed to read block-lookup file {block_lookup_path}: {e}"
        ) from e

    if not isinstance(payload, dict):
        raise ManifestBuildError(
            f"block_lookup file {block_lookup_path} is not a JSON object"
        )

    schema_version: Any = payload.get("schema_version")
    if (
        not isinstance(schema_version, int)
        or schema_version < _MIN_BLOCK_LOOKUP_SCHEMA_VERSION
    ):
        raise ManifestBuildError(
            f"block_lookup file {block_lookup_path} has schema_version "
            f"{schema_version!r} but manifest builder requires "
            f">= {_MIN_BLOCK_LOOKUP_SCHEMA_VERSION}; re-run `pipeline blocks`"
        )

    file_start: Any = payload.get("congress_start")
    file_end: Any = payload.get("congress_end")
    if file_start != expected_congress_start or file_end != expected_congress_end:
        raise ManifestBuildError(
            f"block_lookup file {block_lookup_path} covers Congresses "
            f"{file_start}-{file_end} but project scope is "
            f"{expected_congress_start}-{expected_congress_end}; "
            f"re-run `pipeline blocks`"
        )

    congresses: Any = payload.get("congresses")
    if not isinstance(congresses, list):
        raise ManifestBuildError(
            f"block_lookup file {block_lookup_path} is missing the `congresses` "
            f"field (or it is not a list); re-run `pipeline blocks`"
        )

    return congresses
