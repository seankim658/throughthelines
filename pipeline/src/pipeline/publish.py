from __future__ import annotations

import json
from collections.abc import Collection
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

import boto3
from boto3.exceptions import S3UploadFailedError
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError
from pydantic_settings import BaseSettings, SettingsConfigDict

if TYPE_CHECKING:
    from types_boto3_s3 import S3Client


_MANIFEST_KEY: str = "manifest.json"
_MANIFEST_CACHE_CONTROL: str = "no-cache"
# Versioned and content-addressed artifacts never change for a given key
_IMMUTABLE_CACHE_CONTROL: str = "public, max-age=31536000, immutable"
_ENV_FILE: Path = Path(__file__).resolve().parents[2] / ".env"


# --- Errors ---


class PublishError(Exception):
    """Raised when artifacts cannot be published to R2."""


# --- Models ---


class R2Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="R2_", env_file=_ENV_FILE, extra="ignore"
    )

    access_key_id: str
    secret_access_key: str
    account_id: str
    bucket: str

    @property
    def endpoint_url(self) -> str:
        return f"https://{self.account_id}.r2.cloudflarestorage.com"


@dataclass(frozen=True)
class _PlannedUpload:
    """One file to upload, with its destination key and caching intent."""

    source: Path
    key: str
    skip_if_present: bool


@dataclass(frozen=True)
class PublishResult:
    bucket: str
    url_prefix: str | None
    uploaded: int
    skipped: int
    total_bytes: int
    manifest_key: str
    # (action, key) pairs in upload order, e.g. ("uploaded", "v/abc/members.json").
    outcomes: list[tuple[str, str]]


# --- Key / content-type helpers ---


def _resolve_key(path: str, unversioned: bool, url_prefix: str | None) -> str:
    if unversioned or url_prefix is None:
        return path
    return f"{url_prefix}/{path}"


def _content_type(key: str) -> str:
    if key.endswith(".json"):
        return "application/json"
    return "application/octet-stream"


# --- Upload planning ---


def _plan_global_uploads(
    artifacts: dict[str, Any],
    derived_dir: Path,
    basemap_file: Path,
    url_prefix: str | None,
) -> list[_PlannedUpload]:
    plans: list[_PlannedUpload] = []

    for name in ("plan_index", "members"):
        path: str = artifacts[name]["path"]
        plans.append(
            _PlannedUpload(
                source=derived_dir / path,
                key=_resolve_key(path, unversioned=False, url_prefix=url_prefix),
                skip_if_present=False,
            )
        )

    basemap_path: str = artifacts["basemap"]["path"]
    plans.append(
        _PlannedUpload(
            source=basemap_file,
            key=_resolve_key(basemap_path, unversioned=True, url_prefix=url_prefix),
            skip_if_present=True,
        )
    )
    return plans


def _plan_state_uploads(
    states: dict[str, Any], derived_dir: Path, url_prefix: str | None
) -> list[_PlannedUpload]:
    plans: list[_PlannedUpload] = []
    for state in states.values():
        for chamber in state["chambers"].values():
            for ref in chamber["artifacts"].values():
                path: str = ref["path"]
                plans.append(
                    _PlannedUpload(
                        source=derived_dir / path,
                        key=_resolve_key(
                            path, unversioned=False, url_prefix=url_prefix
                        ),
                        skip_if_present=False,
                    )
                )
    return plans


def _load_manifest(manifest_file: Path) -> dict[str, Any]:
    if not manifest_file.exists():
        raise PublishError(
            f"manifest not found at {manifest_file} (run `pipeline manifest` first)"
        )
    return _load_json_object(manifest_file, "manifest")


def _load_json_object(path: Path, label: str) -> dict[str, Any]:
    if not path.exists():
        raise PublishError(f"{label} not found at {path}")
    with path.open("rb") as f:
        loaded: Any = json.load(f)
    if not isinstance(loaded, dict):
        raise PublishError(
            f"{label} at {path} must be a JSON object; got {type(loaded).__name__}"
        )
    return loaded


# --- Release gate ---


def check_release_states(
    manifest: dict[str, Any], derived_dir: Path, publish_states: Collection[str]
) -> None:
    """Refuse a release whose artifacts hold a state missing from scope.publish.

    Checks the manifest's states and the states inside the plan index and
    members file it names, since those two files cover every state at once.
    """
    problems: list[str] = []
    for label, states in _release_states(manifest, derived_dir):
        unpublished: list[str] = sorted(set(states) - set(publish_states))
        if unpublished:
            problems.append(f"{label} holds {', '.join(unpublished)}")
    if problems:
        raise PublishError(
            "refusing to publish states missing from scope.publish: "
            f"{'; '.join(problems)}. Rebuild plan-index, members and manifest "
            "without --include-unpublished, or add the state to scope.publish."
        )


def _release_states(
    manifest: dict[str, Any], derived_dir: Path
) -> list[tuple[str, list[str]]]:
    """Return each released artifact's name with the states it holds."""
    artifacts: dict[str, Any] = manifest["artifacts"]
    plan_index_path: str = artifacts["plan_index"]["path"]
    members_path: str = artifacts["members"]["path"]
    plan_index = _load_json_object(derived_dir / plan_index_path, "plan index")
    members = _load_json_object(derived_dir / members_path, "members file")
    return [
        ("manifest.json", list(manifest.get("states", {}))),
        (plan_index_path, list(plan_index.get("plans", {}))),
        (members_path, list(members)),
    ]


# --- S3 client + transfers ---


def _make_client(settings: R2Settings) -> S3Client:
    return boto3.client(
        "s3",
        endpoint_url=settings.endpoint_url,
        aws_access_key_id=settings.access_key_id,
        aws_secret_access_key=settings.secret_access_key,
        region_name="auto",
        config=Config(
            retries={"max_attempts": 3, "mode": "standard"},
            request_checksum_calculation="when_required",
            response_checksum_validation="when_required",
        ),
    )


def _object_exists(client: S3Client, bucket: str, key: str) -> bool:
    try:
        client.head_object(Bucket=bucket, Key=key)
        return True
    except ClientError as e:
        code: str = e.response.get("Error", {}).get("Code", "")
        if code in ("404", "NoSuchKey", "NotFound"):
            return False
        raise


def _upload(client: S3Client, bucket: str, source: Path, key: str) -> None:
    if not source.exists():
        raise PublishError(f"artifact missing on disk: {source}")
    cache_control: str = (
        _MANIFEST_CACHE_CONTROL if key == _MANIFEST_KEY else _IMMUTABLE_CACHE_CONTROL
    )
    client.upload_file(
        str(source),
        bucket,
        key,
        ExtraArgs={"ContentType": _content_type(key), "CacheControl": cache_control},
    )


# --- Orchestration ---


def publish_artifacts(
    manifest_file: Path,
    derived_dir: Path,
    basemap_file: Path,
    settings: R2Settings,
    *,
    publish_states: Collection[str],
) -> PublishResult:
    """Upload the manifest's artifacts to R2, then the manifest itself.

    Nothing uploads when any released artifact holds a state missing from
    publish_states.
    """
    manifest: dict[str, Any] = _load_manifest(manifest_file)
    check_release_states(manifest, derived_dir, publish_states)
    url_prefix: str | None = manifest.get("build", {}).get("url_prefix")

    plans: list[_PlannedUpload] = _plan_global_uploads(
        manifest["artifacts"], derived_dir, basemap_file, url_prefix
    )
    plans += _plan_state_uploads(manifest.get("states", {}), derived_dir, url_prefix)

    client: S3Client = _make_client(settings)
    bucket: str = settings.bucket

    uploaded: int = 0
    skipped: int = 0
    total_bytes: int = 0
    outcomes: list[tuple[str, str]] = []

    try:
        for planned in plans:
            if planned.skip_if_present and _object_exists(client, bucket, planned.key):
                skipped += 1
                outcomes.append(("skipped", planned.key))
                continue
            _upload(client, bucket, planned.source, planned.key)
            uploaded += 1
            total_bytes += planned.source.stat().st_size
            outcomes.append(("uploaded", planned.key))

        _upload(client, bucket, manifest_file, _MANIFEST_KEY)
        outcomes.append(("uploaded", _MANIFEST_KEY))
    except (BotoCoreError, ClientError, S3UploadFailedError) as e:
        raise PublishError(f"upload failed: {e}") from e

    return PublishResult(
        bucket=bucket,
        url_prefix=url_prefix,
        uploaded=uploaded,
        skipped=skipped,
        total_bytes=total_bytes,
        manifest_key=_MANIFEST_KEY,
        outcomes=outcomes,
    )
