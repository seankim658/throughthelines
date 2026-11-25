"""Fetch upstream sources referenced in config/sources.toml.

The fetch is split into two scopes:

    fetch_national:
        - Voteview HSall_members.csv (one CSV)
        - Census BEFs (one zip per published Congress)
    fetch_state:
        - Lewis plan polygon GeoJSONs for one state
        - Census tabblock shapefiles (one per vintage, for one state)
        - Block-assignment files with state = <this state>
        - Geometry-source files for one state

Geometry sources carry a pinned sha256. A file that does not match its pin
is never saved, and the fetch fails after trying every source, so a plan is
never built from district lines that changed upstream without review.
"""

from __future__ import annotations

import hashlib
import random
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, Protocol

import yaml

from pipeline.config import FetchConfig, GeometrySource, ProjectPaths, RequestSettings
from pipeline.core.state_codes import SupportedStateCode

DEFAULT_USER_AGENT: str = "through-the-lines-pipeline/0.1"
NATIONAL_FETCH_STATE_FILENAME: str = "_national.yaml"

FetchStatus = Literal["fetched", "unchanged"]

# --- Errors ---


class FetchError(Exception):
    """Raised when a download fails or produces an unexpected result."""


class _ChecksumMismatchError(FetchError):
    """Raised when a pinned file's bytes do not match its pin."""


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
    state: SupportedStateCode | None  # None means national scope


@dataclass(frozen=True)
class HttpResponse:
    """A downloaded body, or None when the server reports it unchanged."""

    body: bytes | None
    headers: dict[str, str]


class Downloader(Protocol):
    def get(self, url: str, headers: dict[str, str]) -> HttpResponse: ...


@dataclass(frozen=True)
class _PriorRecord:
    """Single file entry from a previously-written fetch-state record."""

    etag: str | None
    last_modified: str | None


# --- API ---


def fetch_national(
    sources: FetchConfig, project_paths: ProjectPaths, downloader: Downloader
) -> FetchResult:
    """Fetch Voteview and all Census BEFs."""
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
            downloader,
            prior.get(sources.voteview.url),
        )
    )

    # National block-assignment files
    bef_dir: Path = project_paths.bef_dir
    bef_dir.mkdir(parents=True, exist_ok=True)
    for entry in sources.block_assignments:
        if entry.state != "*":
            continue
        bef_local: Path = bef_dir / Path(entry.url).name
        fetched.append(
            _fetch_one(entry.url, bef_local, downloader, prior.get(entry.url))
        )

    written_path: Path = _write_manifest(sources, fetched, project_paths, manifest_path)
    return FetchResult(files=fetched, state_path=written_path, state=None)


def fetch_state(
    state: SupportedStateCode,
    sources: FetchConfig,
    project_paths: ProjectPaths,
    downloader: Downloader,
) -> FetchResult:
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
                downloader,
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
        fetched.append(_fetch_one(tab_url, tab_local, downloader, prior.get(tab_url)))

    # State-specific block-assignment files
    bef_dir: Path = project_paths.bef_dir
    bef_dir.mkdir(parents=True, exist_ok=True)
    for entry in sources.block_assignments:
        if entry.state != state:
            continue
        bef_local: Path = bef_dir / Path(entry.url).name
        fetched.append(
            _fetch_one(entry.url, bef_local, downloader, prior.get(entry.url))
        )

    geometries: list[GeometrySource] = [
        geometry for geometry in sources.geometry_sources if geometry.state == state
    ]
    fetched.extend(
        _fetch_geometry_sources(geometries, project_paths, downloader, prior)
    )

    written_path: Path = _write_manifest(sources, fetched, project_paths, state_path)
    return FetchResult(files=fetched, state_path=written_path, state=state)


def _fetch_geometry_sources(
    geometries: list[GeometrySource],
    project_paths: ProjectPaths,
    downloader: Downloader,
    prior: dict[str, _PriorRecord],
) -> list[FetchedFile]:
    """Fetch every pinned geometry source, then fail on any mismatch.

    Every source is tried before failing, so one run reports every file that
    changed upstream.
    """
    fetched: list[FetchedFile] = []
    mismatches: list[str] = []
    for geometry in geometries:
        local_path: Path = (
            project_paths.district_geometry_dir
            / geometry.provider
            / geometry.state
            / geometry.local_filename
        )
        try:
            fetched.append(
                _fetch_one(
                    geometry.url,
                    local_path,
                    downloader,
                    prior.get(geometry.url),
                    expected_sha256=geometry.sha256,
                )
            )
        except _ChecksumMismatchError as exc:
            mismatches.append(str(exc))
    if mismatches:
        raise FetchError(
            f"{len(mismatches)} geometry source(s) do not match their pinned "
            f"checksum in sources.toml: {'; '.join(mismatches)}"
        )
    return fetched


# --- Fetch ---


class HttpDownloader:
    """Download over https, retrying transient failures with backoff."""

    def __init__(self, settings: RequestSettings, user_agent: str | None) -> None:
        self._settings = settings
        self._user_agent = DEFAULT_USER_AGENT if user_agent is None else user_agent

    def get(self, url: str, headers: dict[str, str]) -> HttpResponse:
        if not url.startswith("https://"):
            raise FetchError(f"source URLs must use https; got {url!r}")

        request_headers: dict[str, str] = {"User-Agent": self._user_agent, **headers}
        attempts: int = self._settings.max_retry_attempts
        backoff_seconds: float = self._settings.initial_backoff_seconds
        last_exception: urllib.error.URLError | None = None
        for attempt in range(1, attempts + 1):
            try:
                return self._attempt(url, request_headers)
            except urllib.error.URLError as exc:
                last_exception = exc
            if attempt < attempts:
                # Retry jitter needs no cryptographic randomness.
                jitter: float = random.uniform(0, self._settings.jitter_seconds)  # noqa: S311
                time.sleep(backoff_seconds + jitter)
                backoff_seconds *= self._settings.backoff_multiplier

        raise FetchError(
            f"failed to download {url} after {attempts} attempts: {last_exception}"
        ) from last_exception

    def _attempt(self, url: str, request_headers: dict[str, str]) -> HttpResponse:
        """Make one request, raising URLError only for a retryable failure."""
        # get() checks for https, which rules out file: and custom schemes.
        request = urllib.request.Request(url, headers=request_headers)  # noqa: S310
        try:
            with urllib.request.urlopen(  # noqa: S310
                request, timeout=self._settings.request_timeout_seconds
            ) as response:
                return HttpResponse(
                    body=response.read(), headers=dict(response.headers.items())
                )
        except urllib.error.HTTPError as exc:
            if exc.code == 304:
                not_modified_headers: dict[str, str] = (
                    dict(exc.headers.items()) if exc.headers else {}
                )
                return HttpResponse(body=None, headers=not_modified_headers)
            if exc.code in self._settings.retryable_http_codes:
                raise
            raise FetchError(f"HTTP {exc.code} on {url}: {exc.reason}") from exc
        except urllib.error.URLError:
            raise
        except Exception as exc:
            raise FetchError(f"failed to download {url}: {exc}") from exc


def _fetch_one(
    source_url: str,
    local_path: Path,
    downloader: Downloader,
    prior: _PriorRecord | None,
    *,
    expected_sha256: str | None = None,
) -> FetchedFile:
    """Download one file, saving it only if it matches any expected digest."""
    extra_headers: dict[str, str] = _build_conditional_headers(local_path, prior)
    response: HttpResponse = downloader.get(source_url, extra_headers)
    if response.body is None:
        unchanged: FetchedFile = _record_unchanged(
            source_url, local_path, response.headers, prior
        )
        _verify_sha256(unchanged.source_url, unchanged.sha256, expected_sha256)
        return unchanged

    sha256: str = hashlib.sha256(response.body).hexdigest()
    _verify_sha256(source_url, sha256, expected_sha256)
    local_path.parent.mkdir(parents=True, exist_ok=True)
    local_path.write_bytes(response.body)

    return FetchedFile(
        source_url=source_url,
        local_path=local_path,
        sha256=sha256,
        file_bytes=len(response.body),
        etag=response.headers.get("ETag"),
        last_modified=response.headers.get("Last-Modified"),
        status="fetched",
    )


def _verify_sha256(source_url: str, actual: str, expected: str | None) -> None:
    if expected is not None and actual != expected:
        raise _ChecksumMismatchError(
            f"checksum mismatch for {source_url}: pinned {expected}, got {actual}"
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
        "fetched_at": datetime.now(UTC).isoformat(),
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
