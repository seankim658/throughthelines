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

# Wildcard for a block-assignment entry that applies to all states
NATIONAL_SCOPE: Literal["*"] = "*"


# --- Errors ---


class FetchConfigError(ValueError):
    """Raised when sources.toml is missing required fields or malformed."""


# --- Models ---


@dataclass(frozen=True)
class LewisSource:

    repo: str
    commit_sha: str
    landing_url: str
    homepage: str
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
    landing_url: str


@dataclass(frozen=True)
class BlockAssignmentEntry:

    provider: str
    state: SupportedStateCode | Literal["*"]
    congress: int
    vintage: BlockVintage
    url: str
    landing_url: str
    inner_filename: str
    district_column: str
    geoid_column: str | None = None  # None -> auto-detect {"BLOCKID", "GEOID"}
    delimiter: str = ","


@dataclass(frozen=True)
class CensusSource:

    tabblock_templates: dict[BlockVintage, str]

    def tabblock_url(self, vintage: BlockVintage, state: SupportedStateCode) -> str:
        info = STATE_INFO[state]
        template: str = self.tabblock_templates[vintage]
        return template.format(fips=info.fips, name_upper=info.name_upper)


@dataclass(frozen=True)
class ProtomapsBasemapSource:

    build_url: str
    landing_url: str
    max_zoom: int
    bbox: tuple[float, float, float, float]


@dataclass(frozen=True)
class FetchConfig:

    schema_version: int
    lewis: LewisSource
    voteview: VoteviewSource
    census: CensusSource
    block_assignments: list[BlockAssignmentEntry]
    protomaps_basemap: ProtomapsBasemapSource


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
        homepage=require_string(lewis_raw, "homepage", "lewis", path, FetchConfigError),
        states=_load_lewis_states(lewis_raw, path),
    )

    voteview_raw: dict[str, Any] = require_section(
        raw, "voteview", path, FetchConfigError
    )
    voteview = VoteviewSource(
        url=require_string(voteview_raw, "url", "voteview", path, FetchConfigError),
        landing_url=require_string(
            voteview_raw, "landing_url", "voteview", path, FetchConfigError
        ),
    )

    census_raw: dict[str, Any] = require_section(raw, "census", path, FetchConfigError)
    census = _load_census(census_raw, path)

    block_assignments: list[BlockAssignmentEntry] = _load_block_assignments(raw, path)

    protomaps_basemap_raw: dict[str, Any] = require_section(
        raw, "protomaps_basemap", path, FetchConfigError
    )
    protomaps_basemap = ProtomapsBasemapSource(
        build_url=require_string(
            protomaps_basemap_raw,
            "build_url",
            "protomaps_basemap",
            path,
            FetchConfigError,
        ),
        landing_url=require_string(
            protomaps_basemap_raw,
            "landing_url",
            "protomaps_basemap",
            path,
            FetchConfigError,
        ),
        max_zoom=require_int(
            protomaps_basemap_raw,
            "max_zoom",
            "protomaps_basemap",
            path,
            FetchConfigError,
        ),
        bbox=_load_basemap_bbox(protomaps_basemap_raw, path),
    )

    return FetchConfig(
        schema_version=schema_version,
        lewis=lewis,
        voteview=voteview,
        census=census,
        block_assignments=block_assignments,
        protomaps_basemap=protomaps_basemap,
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
    tabblock_templates: dict[BlockVintage, str] = _load_census_tabblock_templates(
        census_raw, path
    )
    return CensusSource(tabblock_templates=tabblock_templates)


def _load_block_assignments(
    raw: dict[str, Any], path: Path
) -> list[BlockAssignmentEntry]:
    if "block_assignment" not in raw:
        raise FetchConfigError(
            f"missing [[block_assignment]] entries in {path}; expected at "
            f"least one entry"
        )
    entries_raw = raw["block_assignment"]
    if not isinstance(entries_raw, list) or not entries_raw:
        raise FetchConfigError(
            f"[[block_assignment]] in {path} must be a non-empty array of tables"
        )

    seen: set[tuple[str, str, int]] = set()
    entries: list[BlockAssignmentEntry] = []
    for idx, entry_raw in enumerate(entries_raw):
        if not isinstance(entry_raw, dict):
            raise FetchConfigError(
                f"[[block_assignment]] entry at index {idx} in {path} is not a table"
            )
        section_label: str = f"block_assignment[{idx}]"

        provider: str = require_string(
            entry_raw, "provider", section_label, path, FetchConfigError
        )

        state_raw: str = require_string(
            entry_raw, "state", section_label, path, FetchConfigError
        )

        if state_raw != NATIONAL_SCOPE and state_raw not in SUPPORTED_STATES:
            supported_list: str = ", ".join(SUPPORTED_STATES)
            raise FetchConfigError(
                f"unknown state {state_raw!r} in [[{section_label}]] in {path} "
                f"(expected '*' or one of: {supported_list})"
            )
        state: SupportedStateCode | Literal["*"] = cast(
            "SupportedStateCode | Literal['*']", state_raw
        )

        congress: int = require_int(
            entry_raw, "congress", section_label, path, FetchConfigError
        )

        dedup_key: tuple[str, str, int] = (provider, state_raw, congress)
        if dedup_key in seen:
            raise FetchConfigError(
                f"duplicate [[block_assignment]] entry for "
                f"provider={provider!r}, state={state_raw!r}, congress={congress} "
                f"in {path}"
            )
        seen.add(dedup_key)

        vintage_raw: str = require_string(
            entry_raw, "vintage", section_label, path, FetchConfigError
        )
        if vintage_raw not in SUPPORTED_VINTAGES:
            supported_vintages: str = ", ".join(SUPPORTED_VINTAGES)
            raise FetchConfigError(
                f"unknown vintage {vintage_raw!r} in [[{section_label}]] in "
                f"{path} (supported: {supported_vintages})"
            )

        url: str = require_string(
            entry_raw, "url", section_label, path, FetchConfigError
        )
        landing_url: str = require_string(
            entry_raw, "landing_url", section_label, path, FetchConfigError
        )
        inner_filename: str = require_string(
            entry_raw, "inner_filename", section_label, path, FetchConfigError
        )
        district_column: str = require_string(
            entry_raw, "district_column", section_label, path, FetchConfigError
        )

        geoid_column_raw: Any = entry_raw.get("geoid_column")
        if geoid_column_raw is not None and not isinstance(geoid_column_raw, str):
            raise FetchConfigError(
                f"geoid_column in [[{section_label}]] in {path} must be a string"
            )
        geoid_column: str | None = geoid_column_raw

        delimiter_raw: Any = entry_raw.get("delimiter", ",")
        if not isinstance(delimiter_raw, str):
            raise FetchConfigError(
                f"delimiter in [[{section_label}]] in {path} must be a string"
            )
        delimiter: str = delimiter_raw

        entries.append(
            BlockAssignmentEntry(
                provider=provider,
                state=state,
                congress=congress,
                vintage=cast(BlockVintage, vintage_raw),
                url=url,
                landing_url=landing_url,
                inner_filename=inner_filename,
                district_column=district_column,
                geoid_column=geoid_column,
                delimiter=delimiter,
            )
        )

    entries.sort(key=lambda e: (e.congress, e.state, e.provider))
    return entries


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


def _load_basemap_bbox(
    section: dict[str, Any], path: Path
) -> tuple[float, float, float, float]:
    """Validate the [protomaps_basemap].bbox value as a 4-tuple of floats.

    Order is [west, south, east, north] in WGS84 degrees.
    """
    if "bbox" not in section:
        raise FetchConfigError(f"missing protomaps_basemap.bbox in {path}")
    raw = section["bbox"]
    if not isinstance(raw, list) or len(raw) != 4:
        raise FetchConfigError(
            f"protomaps_basemap.bbox must be a 4-element list "
            f"[west, south, east, north] in {path}"
        )
    if not all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in raw):
        raise FetchConfigError(
            f"protomaps_basemap.bbox elements must all be numbers in {path}"
        )
    west, south, east, north = (float(v) for v in raw)
    if west >= east:
        raise FetchConfigError(
            f"protomaps_basemap.bbox: west ({west}) must be less than east "
            f"({east}) in {path}"
        )
    if south >= north:
        raise FetchConfigError(
            f"protomaps_basemap.bbox: south ({south}) must be less than north "
            f"({north}) in {path}"
        )
    return (west, south, east, north)
