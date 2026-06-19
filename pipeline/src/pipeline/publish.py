from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TYPE_CHECKING

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError
from pydantic_settings import BaseSettings, SettingsConfigDict

if TYPE_CHECKING:
    from mypy_boto3_s3 import S3Client


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
    with manifest_file.open("rb") as f:
        return json.load(f)


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
    manifest_file: Path, derived_dir: Path, basemap_file: Path, settings: R2Settings
) -> PublishResult:
    manifest: dict[str, Any] = _load_manifest(manifest_file)
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
    except (BotoCoreError, ClientError) as e:
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
