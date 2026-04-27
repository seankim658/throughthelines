"""Loader for config/sources.toml."""

from __future__ import annotations
import tomllib
import urllib.parse
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from pipeline.config._common import (
    require_section,
    require_string,
    require_string_list,
    require_supported_schema_version,
)
from pipeline.state_codes import SUPPORTED_STATES, StateCode

SUPPORTED_SCHEMA_VERSIONS: frozenset[int] = frozenset({1})


# --- Errors ---


class FetchConfigError(ValueError):
    """Raised when sources.toml is missing required fields or malformed."""


# --- Models ---


@dataclass(frozen=True)
class LewisSource:

    repo: str
    commit_sha: str
    states: dict[StateCode, list[str]]

    def raw_url(self, file_path: str) -> str:
        encoded: str = urllib.parse.quote(file_path)
        return (
            f"https://raw.githubusercontent.com/{self.repo}/"
            f"{self.commit_sha}/{encoded}"
        )


@dataclass(frozen=True)
class VoteviewSource:

    url: str


@dataclass(frozen=True)
class FetchConfig:

    schema_version: int
    lewis: LewisSource
    voteview: VoteviewSource


# --- Loader ---


def load_fetch_config(path: Path) -> FetchConfig:
    """Load and validate sources.toml."""

    with path.open("rb") as f:
        raw: dict[str, Any] = tomllib.load(f)

    schema_version: int = require_supported_schema_version(
        raw, SUPPORTED_SCHEMA_VERSIONS, path, FetchConfigError
    )

    lewis_raw: dict[str, Any] = require_section(raw, "lewis", path, FetchConfigError)
    lewis = LewisSource(
        repo=require_string(lewis_raw, "repo", "lewis", path, FetchConfigError),
        commit_sha=require_string(
            lewis_raw, "commit_sha", "lewis", path, FetchConfigError
        ),
        states=_load_lewis_states(lewis_raw, path),
    )

    voteview_raw: dict[str, Any] = require_section(
        raw, "voteview", path, FetchConfigError
    )
    voteview = VoteviewSource(
        url=require_string(voteview_raw, "url", "voteview", path, FetchConfigError),
    )

    return FetchConfig(schema_version=schema_version, lewis=lewis, voteview=voteview)


def _load_lewis_states(
    lewis_raw: dict[str, Any], path: Path
) -> dict[StateCode, list[str]]:
    if "states" not in lewis_raw:
        raise FetchConfigError(f"missing [lewis.states] section in {path}")
    states_raw = lewis_raw["states"]
    if not isinstance(states_raw, dict):
        raise FetchConfigError(f"[lewis.states] must be a table in {path}")
    if not states_raw:
        raise FetchConfigError(
            f"[lewis.states] in {path} must contain at least one state"
        )

    states: dict[StateCode, list[str]] = {}
    for state_code, state_raw in states_raw.items():
        if state_code not in SUPPORTED_STATES:
            supported_list: str = ", ".join(SUPPORTED_STATES)
            raise FetchConfigError(
                f"unknown state code {state_code!r} in [lewis.states] in {path} "
                f"(supported: {supported_list})"
            )
        if not isinstance(states_raw, dict):
            raise FetchConfigError(
                f"[lewis.states.{state_code}] must be a table in {path}"
            )
        files: list[str] = require_string_list(
            state_raw, "files", f"lewis.states.{state_code}", path, FetchConfigError
        )
        states[cast(StateCode, state_code)] = files

    return states
