"""Loader for config/sources.toml."""

from __future__ import annotations
import tomllib
import urllib.parse
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, cast, get_args

from pipeline.core import SUPPORTED_STATES, SupportedStateCode, STATE_INFO
from pipeline.config._common import (
    require_int,
    require_section,
    require_string,
    require_string_list,
    require_supported_schema_version,
)

SUPPORTED_SCHEMA_VERSIONS: frozenset[int] = frozenset({1})

# Decade-vintage labels for Census tabulation block geometry
# v2000 → 2000-Census blocks (used for 107th–112th Congress spatial joins)
# v2010 → 2010-Census blocks (used for 113th–117th BEFs)
# v2020 → 2020-Census blocks (used for 118th–119th BEFs; runtime pivot)
BlockVintage = Literal["v2000", "v2010", "v2020"]
SUPPORTED_VINTAGES: tuple[BlockVintage, ...] = get_args(BlockVintage)


# --- Errors ---


class FetchConfigError(ValueError):
    """Raised when sources.toml is missing required fields or malformed."""


# --- Models ---


@dataclass(frozen=True)
class LewisSource:

    repo: str
    commit_sha: str
    landing_url: str
    states: dict[SupportedStateCode, list[str]]

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
class CensusBefEntry:

    congress: int
    vintage: BlockVintage
    url: str
    landing_url: str
    national_filename: str
    district_column: str


@dataclass(frozen=True)
class CensusSource:

    befs: list[CensusBefEntry]
    tabblock_templates: dict[BlockVintage, str]

    def tabblock_url(self, vintage: BlockVintage, state: SupportedStateCode) -> str:
        info = STATE_INFO[state]
        template: str = self.tabblock_templates[vintage]
        return template.format(fips=info.fips, name_upper=info.name_upper)


@dataclass(frozen=True)
class FetchConfig:

    schema_version: int
    lewis: LewisSource
    voteview: VoteviewSource
    census: CensusSource


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
        landing_url=require_string(
            lewis_raw, "landing_url", "lewis", path, FetchConfigError
        ),
        states=_load_lewis_states(lewis_raw, path),
    )

    voteview_raw: dict[str, Any] = require_section(
        raw, "voteview", path, FetchConfigError
    )
    voteview = VoteviewSource(
        url=require_string(voteview_raw, "url", "voteview", path, FetchConfigError),
    )

    census_raw: dict[str, Any] = require_section(raw, "census", path, FetchConfigError)
    census = _load_census(census_raw, path)

    return FetchConfig(
        schema_version=schema_version, lewis=lewis, voteview=voteview, census=census
    )


def _load_lewis_states(
    lewis_raw: dict[str, Any], path: Path
) -> dict[SupportedStateCode, list[str]]:
    if "states" not in lewis_raw:
        raise FetchConfigError(f"missing [lewis.states] section in {path}")
    states_raw = lewis_raw["states"]
    if not isinstance(states_raw, dict):
        raise FetchConfigError(f"[lewis.states] must be a table in {path}")
    if not states_raw:
        raise FetchConfigError(
            f"[lewis.states] in {path} must contain at least one state"
        )

    states: dict[SupportedStateCode, list[str]] = {}
    for state_code, state_raw in states_raw.items():
        if state_code not in SUPPORTED_STATES:
            supported_list: str = ", ".join(SUPPORTED_STATES)
            raise FetchConfigError(
                f"unknown state code {state_code!r} in [lewis.states] in {path} "
                f"(supported: {supported_list})"
            )
        if not isinstance(state_raw, dict):
            raise FetchConfigError(
                f"[lewis.states.{state_code}] must be a table in {path}"
            )
        files: list[str] = require_string_list(
            state_raw, "files", f"lewis.states.{state_code}", path, FetchConfigError
        )
        states[cast(SupportedStateCode, state_code)] = files

    return states


def _load_census(census_raw: dict[str, Any], path: Path) -> CensusSource:
    befs: list[CensusBefEntry] = _load_census_befs(census_raw, path)
    tabblock_templates: dict[BlockVintage, str] = _load_census_tabblock_templates(
        census_raw, path
    )
    return CensusSource(befs=befs, tabblock_templates=tabblock_templates)


def _load_census_befs(census_raw: dict[str, Any], path: Path) -> list[CensusBefEntry]:
    if "bef" not in census_raw:
        raise FetchConfigError(f"missing [[census.bef]] entries in {path}")
    bef_raw = census_raw["bef"]
    if not isinstance(bef_raw, list) or not bef_raw:
        raise FetchConfigError(
            f"[[census.bef]] in {path} must be a non-empty array of tables"
        )

    seen_congresses: set[int] = set()
    befs: list[CensusBefEntry] = []
    for idx, entry_raw in enumerate(bef_raw):
        if not isinstance(entry_raw, dict):
            raise FetchConfigError(
                f"[[census.bef]] entry at index {idx} in {path} is not a table"
            )
        section_label: str = f"census.bef[{idx}]"
        congress: int = require_int(
            entry_raw, "congress", section_label, path, FetchConfigError
        )
        if congress in seen_congresses:
            raise FetchConfigError(
                f"duplicate [[census.bef]] entry for congress {congress} in {path}"
            )
        seen_congresses.add(congress)

        vintage_raw: str = require_string(
            entry_raw, "vintage", section_label, path, FetchConfigError
        )
        if vintage_raw not in SUPPORTED_VINTAGES:
            supported_list: str = ", ".join(SUPPORTED_VINTAGES)
            raise FetchConfigError(
                f"unknown vintage {vintage_raw!r} in [[{section_label}]] in "
                f"{path} (supported: {supported_list})"
            )

        url: str = require_string(
            entry_raw, "url", section_label, path, FetchConfigError
        )
        landing_url: str = require_string(
            entry_raw, "landing_url", section_label, path, FetchConfigError
        )
        national_filename: str = require_string(
            entry_raw, "national_filename", section_label, path, FetchConfigError
        )
        district_column: str = require_string(
            entry_raw, "district_column", section_label, path, FetchConfigError
        )
        befs.append(
            CensusBefEntry(
                congress=congress,
                vintage=cast(BlockVintage, vintage_raw),
                url=url,
                landing_url=landing_url,
                national_filename=national_filename,
                district_column=district_column,
            )
        )

    befs.sort(key=lambda entry: entry.congress)
    return befs


def _load_census_tabblock_templates(
    census_raw: dict[str, Any], path: Path
) -> dict[BlockVintage, str]:
    tabblock_raw: dict[str, Any] = require_section(
        census_raw, "tabblock", path, FetchConfigError
    )

    templates: dict[BlockVintage, str] = {}
    for vintage_key, vintage_raw in tabblock_raw.items():
        if vintage_key not in SUPPORTED_VINTAGES:
            supported_list = ", ".join(SUPPORTED_VINTAGES)
            raise FetchConfigError(
                f"unknown tabblock vintage {vintage_key!r} in [census.tabblock] in "
                f"{path} (supported: {supported_list})"
            )
        if not isinstance(vintage_raw, dict):
            raise FetchConfigError(
                f"[census.tabblock.{vintage_key}] must be a table in {path}"
            )
        template: str = require_string(
            vintage_raw,
            "url_template",
            f"census.tabblock.{vintage_key}",
            path,
            FetchConfigError,
        )
        if "{fips}" not in template:
            raise FetchConfigError(
                f"census.tabblock.{vintage_key}.url_template missing required "
                f"{{fips}} placeholder in {path}"
            )
        templates[cast(BlockVintage, vintage_key)] = template

    if not templates:
        raise FetchConfigError(
            f"[census.tabblock] in {path} must contain at least one vintage entry"
        )

    return templates
