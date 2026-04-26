"""Fetch upstream sources data sources referenced in config/sources.toml.

Conditional fetching:
    Reads the previous manifest (if any) and uses the recorded ETag / Last-Modified
    per file to send conditional GET requets. If the server responds with a 304, trust
    the local file and recompute hash defensively. If the local file is missing, fetch
    unconditionally regardless of manifest claim.
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

DEFAULT_USER_AGENT: str = "through-the-lines-pipeline/0.1"
MANIFEST_FILENAME: str = "MANIFEST.yaml"

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
    manifest_path: Path


@dataclass(frozen=True)
class _PriorRecord:
    """Single file entry from a previously-written manifest."""

    etag: str | None
    last_modified: str | None


# --- Fetch ---


def fetch_all(
    sources: FetchConfig,
    request_settings: RequestSettings,
    user_agent: str | None,
    project_paths: ProjectPaths,
) -> FetchResult:
    raw_dir = project_paths.raw_dir
    raw_dir.mkdir(parents=True, exist_ok=True)
    user_agent = DEFAULT_USER_AGENT if user_agent is None else user_agent
    prior: dict[str, _PriorRecord] = _read_prior_manifest(raw_dir)

    fetched: list[FetchedFile] = []

    # Lewis files
    lewis_dir = project_paths.lewis_dir
    lewis_dir.mkdir(exist_ok=True)
    for file_path in sources.lewis.files:
        source_url: str = sources.lewis.raw_url(file_path)
        local_path: Path = lewis_dir / Path(file_path).name
        fetched.append(
            _fetch_one(
                source_url,
                local_path,
                request_settings,
                user_agent,
                prior.get(source_url),
            )
        )

    # Voteview file
    voteview_dir = project_paths.voteview_dir
    voteview_dir.mkdir(exist_ok=True)
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

    manifest_path: Path = _write_manifest(sources, fetched, project_paths)
    return FetchResult(files=fetched, manifest_path=manifest_path)


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
    sources: FetchConfig, fetched: list[FetchedFile], project_paths: ProjectPaths
) -> Path:
    manifest_path = project_paths.manifest_file
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
    manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False))
    return manifest_path


def _read_prior_manifest(raw_dir: Path) -> dict[str, _PriorRecord]:
    manifest_path: Path = raw_dir / MANIFEST_FILENAME
    if not manifest_path.exists():
        return {}

    try:
        raw = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
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
