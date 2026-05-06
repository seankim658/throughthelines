"""Fetch upstream sources referenced in config/sources.toml.

The fetch is split into two scopes:

    fetch_national:
        - Voteview HSall_members.csv (one CSV)
        - Census BEFs (one zip per published Congress)
    fetch_state:
        - Lewis plan polygon GeoJSONs for one state
        - Census tabblock shapefiles (one per vintage, for one state)
"""

from __future__ import annotations
import hashlib
import random
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

import yaml

from pipeline.config import FetchConfig, RequestSettings, ProjectPaths
from pipeline.core.state_codes import StateCode

DEFAULT_USER_AGENT: str = "through-the-lines-pipeline/0.1"
NATIONAL_FETCH_STATE_FILENAME: str = "_national.yaml"

FetchStatus = Literal["fetched", "unchanged"]

# --- Errors ---


class FetchError(Exception):
    """Raised when a download fails or produces an unexpected result."""


# --- Models ---


@dataclass(frozen=True)
class FetchedFile:

    source_url: str
    local_path: Path
    sha256: str
    file_bytes: int
    etag: str | None
    last_modified: str | None
    status: FetchStatus


@dataclass(frozen=True)
class FetchResult:

    files: list[FetchedFile]
    state_path: Path
    state: StateCode | None  # None means national scope


@dataclass(frozen=True)
class _PriorRecord:
    """Single file entry from a previously-written fetch-state record."""

    etag: str | None
    last_modified: str | None


# --- API ---


def fetch_national(
    sources: FetchConfig,
    request_settings: RequestSettings,
    user_agent: str | None,
    project_paths: ProjectPaths,
) -> FetchResult:
    """Fetch Voteview and all Census BEFs."""
    user_agent = DEFAULT_USER_AGENT if user_agent is None else user_agent
    project_paths.raw_dir.mkdir(parents=True, exist_ok=True)
    project_paths.fetch_state_dir.mkdir(parents=True, exist_ok=True)

    manifest_path: Path = project_paths.fetch_state_dir / NATIONAL_FETCH_STATE_FILENAME
    prior: dict[str, _PriorRecord] = _read_prior_fetch_state(manifest_path)
    fetched: list[FetchedFile] = []

    # Voteview file
    voteview_dir: Path = project_paths.voteview_dir
    voteview_dir.mkdir(parents=True, exist_ok=True)
    voteview_local: Path = voteview_dir / Path(sources.voteview.url).name
    fetched.append(
        _fetch_one(
            sources.voteview.url,
            voteview_local,
            request_settings,
            user_agent,
            prior.get(sources.voteview.url),
        )
    )

    # Census BEFs (one per published Congress)
    bef_dir: Path = project_paths.bef_dir
    bef_dir.mkdir(parents=True, exist_ok=True)
    for entry in sources.census.befs:
        bef_local: Path = bef_dir / Path(entry.url).name
        fetched.append(
            _fetch_one(
                entry.url, bef_local, request_settings, user_agent, prior.get(entry.url)
            )
        )

    written_path: Path = _write_manifest(sources, fetched, project_paths, manifest_path)
    return FetchResult(files=fetched, state_path=written_path, state=None)


def fetch_state(
    state: StateCode,
    sources: FetchConfig,
    request_settings: RequestSettings,
    user_agent: str | None,
    project_paths: ProjectPaths,
) -> FetchResult:
    user_agent = DEFAULT_USER_AGENT if user_agent is None else user_agent
    project_paths.raw_dir.mkdir(parents=True, exist_ok=True)
    project_paths.fetch_state_dir.mkdir(parents=True, exist_ok=True)

    state_path: Path = project_paths.fetch_state_dir / f"{state}.yaml"
    prior: dict[str, _PriorRecord] = _read_prior_fetch_state(state_path)
    fetched: list[FetchedFile] = []

    # Lewis file
    if state not in sources.lewis.states:
        raise FetchError(
            f"sources.toml [lewis.states] has no entry for states {state!r}"
        )
    lewis_state_dir: Path = project_paths.lewis_dir / state
    lewis_state_dir.mkdir(parents=True, exist_ok=True)
    for file_path in sources.lewis.states[state]:
        source_url: str = sources.lewis.raw_url(file_path)
        local_path: Path = lewis_state_dir / Path(file_path).name
        fetched.append(
            _fetch_one(
                source_url,
                local_path,
                request_settings,
                user_agent,
                prior.get(source_url),
            )
        )

    # Census tabblock zips for every configured vintage
    tabblock_dir: Path = project_paths.tabblock_dir
    for vintage in sources.census.tabblock_templates:
        vintage_year: str = _vintage_to_year(vintage)
        vintage_state_dir: Path = tabblock_dir / vintage_year / state
        vintage_state_dir.mkdir(parents=True, exist_ok=True)
        tab_url: str = sources.census.tabblock_url(vintage, state)
        tab_local: Path = vintage_state_dir / Path(tab_url).name
        fetched.append(
            _fetch_one(
                tab_url, tab_local, request_settings, user_agent, prior.get(tab_url)
            )
        )

    written_path: Path = _write_manifest(sources, fetched, project_paths, state_path)
    return FetchResult(files=fetched, state_path=written_path, state=state)


# --- Fetch ---


def _http_get_with_retry(
    source_url: str,
    settings: RequestSettings,
    user_agent: str,
    extra_headers: dict[str, str] | None = None,
) -> tuple[bytes | None, dict[str, str]]:
    last_exception: Exception | None = None
    backoff_seconds: float = settings.initial_backoff_seconds
    retryable_codes: frozenset[int] = frozenset(settings.retryable_http_codes)

    request_headers: dict[str, str] = {"User-Agent": user_agent}
    if extra_headers:
        request_headers.update(extra_headers)

    for attempt in range(1, settings.max_retry_attempts + 1):
        try:
            request = urllib.request.Request(source_url, headers=request_headers)
            with urllib.request.urlopen(
                request, timeout=settings.request_timeout_seconds
            ) as response:
                body: bytes = response.read()
                headers: dict[str, str] = dict(response.headers.items())
                return body, headers
        except urllib.error.HTTPError as exc:
            if exc.code == 304:
                headers_304: dict[str, str] = (
                    dict(exc.headers.items()) if exc.headers else {}
                )
                return None, headers_304

            last_exception = exc
            if exc.code not in retryable_codes:
                raise FetchError(
                    f"HTTP {exc.code} on {source_url}: {exc.reason}"
                ) from exc
        except urllib.error.URLError as exc:
            last_exception = exc
        except Exception as exc:
            raise FetchError(f"failed to download {source_url}: {exc}") from exc

        if attempt < settings.max_retry_attempts:
            sleep_for: float = backoff_seconds + random.uniform(
                0, settings.jitter_seconds
            )
            time.sleep(sleep_for)
            backoff_seconds *= settings.backoff_multiplier

    raise FetchError(
        f"failed to download {source_url} after {settings.max_retry_attempts} attempts: "
        f"{last_exception}"
    ) from last_exception


def _fetch_one(
    source_url: str,
    local_path: Path,
    settings: RequestSettings,
    user_agent: str,
    prior: _PriorRecord | None,
) -> FetchedFile:
    extra_headers: dict[str, str] = _build_conditional_headers(local_path, prior)
    body, headers = _http_get_with_retry(
        source_url, settings, user_agent, extra_headers
    )
    if body is None:
        return _record_unchanged(source_url, local_path, headers, prior)

    local_path.parent.mkdir(parents=True, exist_ok=True)
    local_path.write_bytes(body)

    return FetchedFile(
        source_url=source_url,
        local_path=local_path,
        sha256=hashlib.sha256(body).hexdigest(),
        file_bytes=len(body),
        etag=headers.get("ETag"),
        last_modified=headers.get("Last-Modified"),
        status="fetched",
    )


def _build_conditional_headers(
    local_path: Path, prior: _PriorRecord | None
) -> dict[str, str]:
    if prior is None or not local_path.exists():
        return {}

    headers: dict[str, str] = {}
    if prior.etag:
        headers["If-None-Match"] = prior.etag
    if prior.last_modified:
        headers["If-Modified-Since"] = prior.last_modified
    return headers


def _record_unchanged(
    source_url: str,
    local_path: Path,
    response_headers: dict[str, str],
    prior: _PriorRecord | None,
) -> FetchedFile:
    if not local_path.exists():
        raise FetchError(
            f"server returned 304 for {source_url} but local file is missing: "
            f"{local_path}"
        )

    data: bytes = local_path.read_bytes()
    etag: str | None = response_headers.get("ETag") or (prior.etag if prior else None)
    last_modified: str | None = response_headers.get("Last-Modified") or (
        prior.last_modified if prior else None
    )

    return FetchedFile(
        source_url=source_url,
        local_path=local_path,
        sha256=hashlib.sha256(data).hexdigest(),
        file_bytes=len(data),
        etag=etag,
        last_modified=last_modified,
        status="unchanged",
    )


# --- Manifest ---


def _write_manifest(
    sources: FetchConfig,
    fetched: list[FetchedFile],
    project_paths: ProjectPaths,
    state_path: Path,
) -> Path:
    state_path.parent.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, Any] = {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "lewis_commit_sha": sources.lewis.commit_sha,
        "files": [
            {
                "source_url": item.source_url,
                "local_path": str(item.local_path.relative_to(project_paths.raw_dir)),
                "sha256": item.sha256,
                "bytes": item.file_bytes,
                "etag": item.etag,
                "last_modified": item.last_modified,
            }
            for item in fetched
        ],
    }
    state_path.write_text(yaml.safe_dump(manifest, sort_keys=False))
    return state_path


def _read_prior_fetch_state(state_path: Path) -> dict[str, _PriorRecord]:
    if not state_path.exists():
        return {}

    try:
        raw = yaml.safe_load(state_path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return {}

    if not isinstance(raw, dict):
        return {}

    files = raw.get("files")
    if not isinstance(files, list):
        return {}

    out: dict[str, _PriorRecord] = {}
    for entry in files:
        if not isinstance(entry, dict):
            continue
        source_url = entry.get("source_url")
        if not isinstance(source_url, str):
            continue
        etag_value = entry.get("etag")
        last_modified_value = entry.get("last_modified")
        out[source_url] = _PriorRecord(
            etag=etag_value if isinstance(etag_value, str) else None,
            last_modified=(
                last_modified_value if isinstance(last_modified_value, str) else None
            ),
        )

    return out


# --- Helpers ---


def _vintage_to_year(vintage: str) -> str:
    if not vintage.startswith("v"):
        raise ValueError(f"unexpected vintage format: {vintage!r}")
    return vintage[1:]
