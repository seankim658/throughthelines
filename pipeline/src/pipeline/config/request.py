"""Loader for config/request.toml."""

from __future__ import annotations
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pipeline.config._common import (
    require_section,
    require_int,
    require_float,
    require_int_list,
    require_supported_schema_version,
)

SUPPORTED_SCHEMA_VERSIONS: frozenset[int] = frozenset({1})

# --- Errors ---


class RequestConfigError(ValueError):
    """Raised when request.toml is missing required fields or malformed."""


# --- Models ---


@dataclass(frozen=True)
class RequestSettings:

    max_retry_attempts: int
    initial_backoff_seconds: float
    backoff_multiplier: float
    request_timeout_seconds: float
    jitter_seconds: float
    retryable_http_codes: list[int]


@dataclass(frozen=True)
class RequestConfig:

    schema_version: int
    request_settings: RequestSettings


# --- Loader ---


def load_request_config(path: Path) -> RequestConfig:
    """Load and validate request.toml."""

    with path.open("rb") as f:
        raw: dict[str, Any] = tomllib.load(f)

    schema_version: int = require_supported_schema_version(
        raw, SUPPORTED_SCHEMA_VERSIONS, path, RequestConfigError
    )

    request_settings_raw: dict[str, Any] = require_section(
        raw, "request", path, RequestConfigError
    )
    request_settings = RequestSettings(
        max_retry_attempts=require_int(
            request_settings_raw,
            "max_retry_attempts",
            "request",
            path,
            RequestConfigError,
        ),
        initial_backoff_seconds=require_float(
            request_settings_raw,
            "initial_backoff_seconds",
            "request",
            path,
            RequestConfigError,
        ),
        backoff_multiplier=require_float(
            request_settings_raw,
            "backoff_multiplier",
            "request",
            path,
            RequestConfigError,
        ),
        request_timeout_seconds=require_float(
            request_settings_raw,
            "request_timeout_seconds",
            "request",
            path,
            RequestConfigError,
        ),
        jitter_seconds=require_float(
            request_settings_raw,
            "jitter_seconds",
            "request",
            path,
            RequestConfigError,
        ),
        retryable_http_codes=require_int_list(
            request_settings_raw,
            "retryable_http_codes",
            "request",
            path,
            RequestConfigError,
        ),
    )

    return RequestConfig(
        schema_version=schema_version, request_settings=request_settings
    )
