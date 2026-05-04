"""Build per-state block-lookup JSON.

Produces `block_lookup_{STATE}.json`, a hash table-friendly artifact
keyed by 2020 Census block GEOID. Maps each block to a per-Congress
district-history array (one slot per Congress in scope).
"""

from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path

from pipeline.config import (
    BlockVintage,
    CensusSource,
    CensusBefEntry,
    ProjectPaths,
    ScopeSettings,
)
from pipeline.core import STATE_INFO, StateCode, write_json_atomic
from pipeline.plans import Plan
from pipeline.blocks.readers import (
    TABBLOCK_COLUMNS,
    load_bef,
    load_block_polygons,
    load_centroids,
    load_lewis_polygons,
)
from pipeline.blocks.stages import cross_decade_join, lewis_spatial_join

_OUTPUT_SCHEMA_VERSION: int = 1

# --- Errors ---


class BlocksBuildError(Exception):
    """Raised when the block-lookup build cannot complete."""


# --- Validation Models ---


@dataclass(frozen=True)
class _BefSource:

    congress: int
    bef_zip_path: Path
    inner_filename: str
    block_vintage: BlockVintage


@dataclass(frozen=True)
class _LewisSource:

    congress: int
    geojson_path: Path
    plan_id: str
    district_property: str = "district"


_CongressSource = _BefSource | _LewisSource


@dataclass(frozen=True)
class _BuildPlan:

    state: StateCode
    scope: ScopeSettings
    state_fips: str
    tabblock_paths: dict[BlockVintage, Path]
    sources: dict[int, _CongressSource]
    unsourced: list[int]


# Block-vintage assignment for pre-BEF Congress (pre 112th)
#
# The build-time decision is to spatially join their plans against 2000-decade tabulation blocks.
_PRE_BEF_VINTAGE: BlockVintage = "v2000"

# First Congress for which a Congress BEF is expected
_FIRST_BEF_CONGRESS: int = 113


# --- Models ---


@dataclass(frozen=True)
class BlocksBuildResult:

    state: StateCode
    output_path: Path
    blocks_count: int
    histories_count: int
    unsourced_congresses: list[int]
    warnings: list[str]


# --- Validation ---


def _validate_inputs(
    plans: list[Plan],
    state: StateCode,
    scope: ScopeSettings,
    project_paths: ProjectPaths,
    census_source: CensusSource,
    allow_missing: bool,
) -> _BuildPlan:
    """Run the upfront checks. Return a frozen build-plan or raise.

    Checks:
        1. Required tabblock zip exists on disk for every BlockVintage referenced
           by the sourcing matrix.
        2. The in-scope plan set covers [congress_start, congress_end] with with
           no duplicates.
        3. Every Congress in scope maps to a BEF entry (with its zip on disk) or
           to an in-scope plan (with its Lewis GeoJSON on disk). Plans that span
           multiple Congresses but lack a BEF drive spatial joins for every Congress
           in their range.
    """
    state_info = STATE_INFO[state]
    bef_by_congress = {e.congress: e for e in census_source.befs}
    in_scope_congresses: list[int] = list(
        range(scope.congress_start, scope.congress_end + 1)
    )

    # Plan-set coverage: every in-scope Congress claimed exactly once
    plan_by_congress: dict[int, Plan] = {}
    for plan in plans:
        plan_end: int = (
            plan.congress_end if plan.congress_end is not None else scope.congress_end
        )
        for congress in range(plan.congress_start, plan_end + 1):
            if congress < scope.congress_start or congress > scope.congress_end:
                continue
            if congress in plan_by_congress:
                raise BlocksBuildError(
                    f"two plans claim Congress {congress} for state {state}: "
                    f"{plan_by_congress[congress].plan_id!r} and {plan.plan_id!r}"
                )
            plan_by_congress[congress] = plan

    uncovered: list[int] = [c for c in in_scope_congresses if c not in plan_by_congress]
    if uncovered:
        raise BlocksBuildError(
            f"no in-scope plan covers Congress(es) {uncovered} for state {state}"
        )

    # Per-Congress sourcing
    sources: dict[int, _CongressSource] = {}
    unsourced: list[int] = []
    needed_vintages: set[BlockVintage] = set()

    bef_dir: Path = project_paths.bef_dir

    for congress in in_scope_congresses:
        plan = plan_by_congress[congress]
        bef_entry: CensusBefEntry | None = bef_by_congress.get(congress)

        if bef_entry is not None:
            bef_zip_path: Path = bef_dir / Path(bef_entry.url).name
            if not bef_zip_path.exists():
                raise BlocksBuildError(
                    f"BEF zip for Congress {congress} not found at {bef_zip_path} "
                    f"(did you run `pipeline fetch`?)"
                )
            vintage: BlockVintage = bef_entry.vintage
            sources[congress] = _BefSource(
                congress=congress,
                bef_zip_path=bef_zip_path,
                inner_filename=bef_entry.national_filename,
                block_vintage=vintage,
            )
            needed_vintages.add(vintage)
            continue

        # No BEF for this Congress, two cases:
        #
        #   1. Pre-BEF era (pre-112th). Census never published BEFs for these Congresses,
        #      so cmopute district-per-block by spatial join against the Lewis plan polygons.
        #   2. BEF era (113+) but the BEF isn't on disk. Do not silently substitue Lewis spatial
        #      join here. Either abort (default) or fill the column with null and continue.
        if congress < _FIRST_BEF_CONGRESS:
            geojson_path: Path = project_paths.raw_dir / plan.source_file
            if not geojson_path.exists():
                raise BlocksBuildError(
                    f"Lewis GeoJSON for plan {plan.plan_id!r} (Congress {congress}) "
                    f"not found at {geojson_path} "
                    f"(did you run `pipeline fetch`?)"
                )
            sources[congress] = _LewisSource(
                congress=congress, geojson_path=geojson_path, plan_id=plan.plan_id
            )
            needed_vintages.add(_PRE_BEF_VINTAGE)
        else:
            if not allow_missing:
                raise BlocksBuildError(
                    f"no BEF configured for Congress {congress} (state {state}); "
                    f"expected in BEF era ({_FIRST_BEF_CONGRESS}th+). "
                    f"Use --allow-missing to skip."
                )
            unsourced.append(congress)

    # Tabblock paths
    needed_vintages.add("v2020")
    if "v2000" in needed_vintages:
        needed_vintages.add("v2010")

    tabblock_paths: dict[BlockVintage, Path] = {}
    for vintage in sorted(needed_vintages):
        if vintage not in census_source.tabblock_templates:
            raise BlocksBuildError(
                f"tabblock vintage {vintage} required by sourcing matrix but "
                f"no url_template configured in sources.toml [census.tabblock]"
            )
        year: str = vintage[1:]
        tab_url: str = census_source.tabblock_url(vintage, state)
        expected_path: Path = (
            project_paths.tabblock_dir / year / state / Path(tab_url).name
        )
        if not expected_path.exists():
            raise BlocksBuildError(
                f"tabblock zip for vintage {vintage} / state {state} not found "
                f"at {expected_path} (did you run `pipeline fetch`?)"
            )
        tabblock_paths[vintage] = expected_path

    return _BuildPlan(
        state=state,
        scope=scope,
        state_fips=state_info.fips,
        tabblock_paths=tabblock_paths,
        sources=sources,
        unsourced=unsourced,
    )


# --- API ---


def build_blocks(
    plans: list[Plan],
    state: StateCode,
    scope: ScopeSettings,
    project_paths: ProjectPaths,
    census_source: CensusSource,
    output_path: Path,
    allow_missing: bool = False,
) -> BlocksBuildResult:
    """Build the per-state block-lookup JSON for one state."""
    build_plan: _BuildPlan = _validate_inputs(
        plans=plans,
        state=state,
        scope=scope,
        project_paths=project_paths,
        census_source=census_source,
        allow_missing=allow_missing,
    )

    # Stage A: load 2020 block centroids
    centroids_2020 = load_centroids(
        tabblock_path=build_plan.tabblock_paths["v2020"],
        columns=TABBLOCK_COLUMNS["v2020"],
        state_fips=build_plan.state_fips,
    )

    # Stage B: spatial-join 2020 centroids against 2010 polygons
    polys_2010, centroids_2010 = load_block_polygons(
        tabblock_path=build_plan.tabblock_paths["v2010"],
        columns=TABBLOCK_COLUMNS["v2010"],
        state_fips=build_plan.state_fips,
    )
    join_2020_to_2010 = cross_decade_join(
        source_centroids=centroids_2020,
        target_polygons=polys_2010,
        target_geoid_col=TABBLOCK_COLUMNS["v2010"].geoid,
        target_centroids=centroids_2010,
    )
    del polys_2010

    # Stage C: spatial-join 2010 centroids against 2000 polygons
    polys_2000, centroids_2000 = load_block_polygons(
        tabblock_path=build_plan.tabblock_paths["v2000"],
        columns=TABBLOCK_COLUMNS["v2000"],
        state_fips=build_plan.state_fips,
    )
    join_2010_to_2000 = cross_decade_join(
        source_centroids=join_2020_to_2010.target_centroids,
        target_polygons=polys_2000,
        target_geoid_col=TABBLOCK_COLUMNS["v2000"].geoid,
        target_centroids=centroids_2000,
    )
    del polys_2000

    # Stage D: chain {geoid_2020: (geoid_2010, geoid_2000)}
    block_linkage: dict[str, tuple[str, str]] = {}
    linkage_warnings: list[str] = []
    for geoid_2020 in centroids_2020:
        geoid_2010 = join_2020_to_2010.linkage.get(geoid_2020)
        if geoid_2010 is None:
            continue
        geoid_2000 = join_2010_to_2000.linkage.get(geoid_2010)
        if geoid_2000 is None:
            continue
        block_linkage[geoid_2020] = (geoid_2010, geoid_2000)

    dropped_at_2010: int = len(centroids_2020) - len(join_2020_to_2010.linkage)
    dropped_at_2000: int = len(join_2020_to_2010.linkage) - len(block_linkage)
    if dropped_at_2010 > 0:
        linkage_warnings.append(
            f"{dropped_at_2010} 2020 block(s) unmatched in 2020 → 2010 join"
        )
    if dropped_at_2000 > 0:
        linkage_warnings.append(
            f"{dropped_at_2000} 2010 block(s) unmatched in 2010 → 2000 join"
        )

    # Free linkage intermediates
    del join_2020_to_2010, join_2010_to_2000, centroids_2010

    # Stage E: load BEF assignments per congress
    # Each BEF dict is keyed by the decade-appropriate GEOID
    bef_assignments: dict[int, dict[str, int]] = {}
    for congress, source in build_plan.sources.items():
        if not isinstance(source, _BefSource):
            continue
        bef_assignments[congress] = load_bef(
            bef_zip_path=source.bef_zip_path,
            inner_filename=source.inner_filename,
            state_fips=build_plan.state_fips,
        )

    # Stage F: Lewis spatial joins, deduplicated by plan_id
    # Multiple congresses can share a plan, so we join once
    # per plan and reuse the result for every congress it covers.
    lewis_assignments: dict[str, dict[str, int]] = {}
    for source in build_plan.sources.values():
        if not isinstance(source, _LewisSource):
            continue
        if source.plan_id in lewis_assignments:
            continue
        plan_polys, district_col = load_lewis_polygons(
            geojson_path=source.geojson_path, district_property=source.district_property
        )
        lewis_assignments[source.plan_id] = lewis_spatial_join(
            centroids=centroids_2000,
            plan_polygons=plan_polys,
            district_col=district_col,
        )
        del plan_polys

    del centroids_2000

    # Stage G: build per-block history arrays
    congress_count: int = scope.congress_end - scope.congress_start + 1
    histories_by_block: dict[str, list[int | None]] = {}

    for geoid_2020 in centroids_2020:
        linkage_entry = block_linkage.get(geoid_2020)
        history: list[int | None] = [None] * congress_count

        for congress in range(scope.congress_start, scope.congress_end + 1):
            idx: int = congress - scope.congress_start
            congress_source = build_plan.sources.get(congress)

            if congress_source is None:
                # Unsourced congress (e.g., 117th)
                continue

            if isinstance(congress_source, _BefSource):
                bef_dict = bef_assignments[congress]
                if congress_source.block_vintage == "v2020":
                    district = bef_dict.get(geoid_2020)
                elif congress_source.block_vintage == "v2010":
                    geoid_2010 = linkage_entry[0] if linkage_entry else None
                    district = bef_dict.get(geoid_2010) if geoid_2010 else None
                else:
                    district = None
                history[idx] = district

            elif isinstance(congress_source, _LewisSource):
                geoid_2000 = linkage_entry[1] if linkage_entry else None
                if geoid_2000 is not None:
                    lewis_dict = lewis_assignments[congress_source.plan_id]
                    history[idx] = lewis_dict.get(geoid_2000)

        histories_by_block[geoid_2020] = history

    history_to_index: dict[tuple[int | None, ...], int] = {}
    unique_histories: list[list[int | None]] = []
    blocks_map: dict[str, int] = {}

    for geoid, history in sorted(histories_by_block.items()):
        key: tuple[int | None, ...] = tuple(history)
        if key not in history_to_index:
            history_to_index[key] = len(unique_histories)
            unique_histories.append(history)
        blocks_map[geoid] = history_to_index[key]

    del histories_by_block

    output_path.parent.mkdir(parents=True, exist_ok=True)
    write_json_atomic(
        output_path,
        {
            "schema_version": _OUTPUT_SCHEMA_VERSION,
            "state": state,
            "congress_start": scope.congress_start,
            "congress_end": scope.congress_end,
            "histories": unique_histories,
            "blocks": blocks_map,
        },
    )

    warnings: list[str] = linkage_warnings + [
        f"{len(block_linkage)} of {len(centroids_2020)} 2020 blocks linked "
        f"across all decades"
    ]

    return BlocksBuildResult(
        state=state,
        output_path=output_path,
        blocks_count=len(blocks_map),
        histories_count=len(unique_histories),
        unsourced_congresses=build_plan.unsourced,
        warnings=warnings,
    )
