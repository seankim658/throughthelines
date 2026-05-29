"""Build per-state block-lookup JSON.

Produces `block_lookup_{STATE}.json`, a hash table-friendly artifact
keyed by 2020 Census block GEOID. Maps each block to a per-Congress
district-history array (one slot per Congress in scope).
"""

from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pipeline.config import (
    BlockAssignmentEntry,
    BlockVintage,
    CensusSource,
    NATIONAL_SCOPE,
    ProjectPaths,
    ScopeSettings,
)
from pipeline.core import (
    STATE_INFO,
    SupportedChamberType,
    SupportedStateCode,
    write_json_atomic,
)
from pipeline.plans import Plan
from pipeline.blocks.readers import (
    TABBLOCK_COLUMNS,
    Centroid,
    load_block_polygons,
    load_centroids,
)
from pipeline.blocks.sources import (
    BlockAssignmentSource,
    BlockGeometry,
    DelimitedAssignmentSource,
    PolygonJoinSource,
    UnsourcedSource,
)
from pipeline.blocks.spatial_joins import (
    CrossDecadeResult,
    cross_decade_join,
)

_OUTPUT_SCHEMA_VERSION: int = 1

# Block-vintage assignment for pre-BEF Congress (pre 113th and post 90s)
_PRE_BEF_VINTAGE: BlockVintage = "v2000"

# First Congress for which a Census BEF is expected
_FIRST_BEF_CONGRESS: int = 113

# --- Errors ---


class BlocksBuildError(Exception):
    """Raised when the block-lookup build cannot complete."""


# --- Internal Models ---


@dataclass(frozen=True)
class _BuildPlan:

    state: SupportedStateCode
    scope: ScopeSettings
    state_fips: str
    tabblock_paths: dict[BlockVintage, Path]
    sources: dict[int, BlockAssignmentSource]
    plan_by_congress: dict[int, Plan]
    resolution_warnings: list[str]


@dataclass(frozen=True)
class _BlockLinkage:
    """Cross-decade linkage of 2020 blocks to their 2010 and 2000 equivalents."""

    centroids_2020: dict[str, Centroid]
    centroids_2010: dict[str, Centroid] | None
    centroids_2000: dict[str, Centroid] | None
    linkage_2020_to_2010: dict[str, str] | None
    linkage_2020_to_2000: dict[str, str] | None
    warnings: list[str]


# --- Models ---


@dataclass(frozen=True)
class BlocksBuildResult:

    state: SupportedStateCode
    output_path: Path
    blocks_count: int
    histories_count: int
    unsourced_congresses: list[int]
    warnings: list[str]


# --- Validation ---


def _validate_inputs(
    plans: list[Plan],
    state: SupportedStateCode,
    scope: ScopeSettings,
    project_paths: ProjectPaths,
    census_source: CensusSource,
    block_assignments: list[BlockAssignmentEntry],
    allow_missing: bool,
    spatial_join_fallback: bool,
    lewis_landing_url: str,
) -> _BuildPlan:
    """Run the upfront checks. Return a frozen build-plan or raise.

    Checks:
        1. Required tabblock zip exists on disk for every BlockVintage referenced
           by the sourcing matrix.
        2. The in-scope plan set covers [congress_start, congress_end] with with
           no duplicates.
        3. Every Congress in scope resolves to a source: a `[[block_assignment]]` entry (state-specific
           or national, with its zip on disk), the pre-BEF polygon fallback, the `--spatial-join-fallback`
           opt-in, or an unsourced placeholder under `--allow-missing`.

    """
    state_info = STATE_INFO[state]

    assignments_by_key: dict[tuple[str, int], BlockAssignmentEntry] = {
        (entry.state, entry.congress): entry for entry in block_assignments
    }

    plan_by_congress: dict[int, Plan] = _resolve_plan_coverage(plans, state, scope)
    sources, needed_vintages, resolution_warnings = _resolve_congress_sources(
        plan_by_congress=plan_by_congress,
        scope=scope,
        assignments_by_key=assignments_by_key,
        project_paths=project_paths,
        state=state,
        allow_missing=allow_missing,
        spatial_join_fallback=spatial_join_fallback,
        lewis_landing_url=lewis_landing_url,
    )
    tabblock_paths: dict[BlockVintage, Path] = _resolve_tabblock_paths(
        needed_vintages=needed_vintages,
        state=state,
        project_paths=project_paths,
        census_source=census_source,
    )

    return _BuildPlan(
        state=state,
        scope=scope,
        state_fips=state_info.fips,
        tabblock_paths=tabblock_paths,
        sources=sources,
        plan_by_congress=plan_by_congress,
        resolution_warnings=resolution_warnings,
    )


def _resolve_plan_coverage(
    plans: list[Plan], state: SupportedStateCode, scope: ScopeSettings
) -> dict[int, Plan]:
    """Map each in-scope Congress to the plan that claims it.

    Plans with `congress_end is None` extend forward to `scope.congress_end`.
    """
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

    uncovered: list[int] = [
        c
        for c in range(scope.congress_start, scope.congress_end + 1)
        if c not in plan_by_congress
    ]
    if uncovered:
        raise BlocksBuildError(
            f"no in-scope plan covers Congress(es) {uncovered} for state {state}"
        )

    return plan_by_congress


def _resolve_congress_sources(
    plan_by_congress: dict[int, Plan],
    scope: ScopeSettings,
    assignments_by_key: dict[tuple[str, int], BlockAssignmentEntry],
    project_paths: ProjectPaths,
    state: SupportedStateCode,
    allow_missing: bool,
    spatial_join_fallback: bool,
    lewis_landing_url: str,
) -> tuple[dict[int, BlockAssignmentSource], set[BlockVintage], list[str]]:
    """Decide a `BlockAssignmentSource` for each in-scope Congress.

    Resolution order, per Congress:
        1. State-specific [[block_assignment]] entry
        2. National [[block_assignment]] entry (state = "*")
        3. Pre-BEF polygon fallback (unconditional below _FIRST_BEF_CONGRESS)
        4. BEF-era polygon fallback under --spatial-join-fallback
        5. Unsourced under --allow-missing
        6. Rasises BlocksBuildError
    """
    sources: dict[int, BlockAssignmentSource] = {}
    needed_vintages: set[BlockVintage] = set()
    polygon_fallback_congresses: list[int] = []
    state_fips: str = STATE_INFO[state].fips

    for congress in range(scope.congress_start, scope.congress_end + 1):
        plan: Plan = plan_by_congress[congress]

        # Step 1: state-specific delimited entry wins
        entry: BlockAssignmentEntry | None = assignments_by_key.get((state, congress))

        # Step 2: national delimited entry
        if entry is None:
            entry = assignments_by_key.get((NATIONAL_SCOPE, congress))

        if entry is not None:
            sources[congress] = _make_delimited_source(
                entry=entry,
                congress=congress,
                state_fips=state_fips,
                bef_dir=project_paths.bef_dir,
            )
            needed_vintages.add(entry.vintage)
            continue

        # Step 3: pre-BEF polygon fallback (unconditional)
        if congress < _FIRST_BEF_CONGRESS:
            sources[congress] = _make_polygon_source(
                plan=plan,
                congress=congress,
                raw_dir=project_paths.raw_dir,
                lewis_landing_url=lewis_landing_url,
            )
            needed_vintages.add(_PRE_BEF_VINTAGE)
            polygon_fallback_congresses.append(congress)
            continue

        # Step 4: BEF-era polygon fallback under --spatial-join-fallback
        if spatial_join_fallback:
            try:
                sources[congress] = _make_polygon_source(
                    plan=plan,
                    congress=congress,
                    raw_dir=project_paths.raw_dir,
                    lewis_landing_url=lewis_landing_url,
                )
                needed_vintages.add(_PRE_BEF_VINTAGE)
                polygon_fallback_congresses.append(congress)
                continue
            except BlocksBuildError:
                if allow_missing:
                    sources[congress] = UnsourcedSource()
                    continue
                raise

        # Step 5: unsourced under --allow-missing
        if allow_missing:
            sources[congress] = UnsourcedSource()
            continue

        # Step 6: error
        raise BlocksBuildError(
            f"no block-assignment entry configured for Congress {congress} "
            f"(state {state}); expected in BEF era ({_FIRST_BEF_CONGRESS}th+). "
            f"Use --allow-missing or --spatial-join-fallback to proceed."
        )

    resolution_warnings: list[str] = []
    if polygon_fallback_congresses:
        resolution_warnings.append(
            f"Polygon-fallback vintage: Congresses "
            f"{sorted(polygon_fallback_congresses)} sourced via "
            f"PolygonJoinSource declared block_vintage={_PRE_BEF_VINTAGE}."
        )

    return sources, needed_vintages, resolution_warnings


def _make_delimited_source(
    entry: BlockAssignmentEntry, congress: int, state_fips: str, bef_dir: Path
) -> DelimitedAssignmentSource:
    """Resolve and validate a delimited-assignment for one Congress."""
    zip_path: Path = bef_dir / Path(entry.url).name
    try:
        return DelimitedAssignmentSource(
            zip_path=zip_path,
            inner_filename=entry.inner_filename,
            state_fips=state_fips,
            district_column=entry.district_column,
            _block_vintage=entry.vintage,
            provider=entry.provider,
            upstream_url=entry.url,
            upstream_landing_url=entry.landing_url,
            geoid_column=entry.geoid_column,
            delimiter=entry.delimiter,
        )
    except FileNotFoundError as e:
        raise BlocksBuildError(
            f"block-assignment zip for Congress {congress} "
            f"(provider={entry.provider!r}) not found at {zip_path} "
            f"(did you run `pipeline fetch`?)"
        ) from e


def _make_polygon_source(
    plan: Plan, congress: int, raw_dir: Path, lewis_landing_url: str
) -> PolygonJoinSource:
    """Resolve and validate a polygon-join source for one Congress."""
    geojson_path: Path = raw_dir / plan.source_file
    try:
        return PolygonJoinSource(
            geojson_path=geojson_path,
            source_file=plan.source_file,
            _block_vintage=_PRE_BEF_VINTAGE,
            provider="lewis",
            upstream_landing_url=lewis_landing_url,
        )
    except FileNotFoundError as e:
        raise BlocksBuildError(
            f"polygon file for plan {plan.plan_id!r} (Congress {congress}) "
            f"not found at {geojson_path} "
            f"(did you run `pipeline fetch`?)"
        ) from e


def _resolve_tabblock_paths(
    needed_vintages: set[BlockVintage],
    state: SupportedStateCode,
    project_paths: ProjectPaths,
    census_source: CensusSource,
) -> dict[BlockVintage, Path]:
    """Verify the tabblock zip exists on disk for every needed vintage."""
    needed_vintages = set(needed_vintages)
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

    return tabblock_paths


# --- Helpers ---


def _classify_linkage_needs(build_plan: _BuildPlan) -> tuple[bool, bool]:
    """Determine which cross-decade linkages the sourcing matrix requires."""
    vintages: set[BlockVintage] = {
        v for s in build_plan.sources.values() if (v := s.block_vintage) is not None
    }
    needs_2010: bool = "v2010" in vintages
    needs_2000: bool = "v2000" in vintages
    return needs_2010, needs_2000


def _summarize_linkage(linkage: _BlockLinkage) -> str:
    total: int = len(linkage.centroids_2020)
    if linkage.linkage_2020_to_2000 is not None:
        return (
            f"{len(linkage.linkage_2020_to_2000)} of {total} 2020 blocks "
            f"linked through to 2000 vintage"
        )
    if linkage.linkage_2020_to_2010 is not None:
        return (
            f"{len(linkage.linkage_2020_to_2010)} of {total} 2020 blocks "
            f"linked to 2010 vintage"
        )
    return f"{total} 2020 blocks loaded; no cross-decade linkage required"


def _build_block_geometry(linkage: _BlockLinkage) -> BlockGeometry:
    """Bundle the centroid dicts the linkage stage loaded into a BlockGeometry."""
    centroids_by_vintage: dict[BlockVintage, dict[str, Centroid]] = {
        "v2020": linkage.centroids_2020
    }
    if linkage.centroids_2010 is not None:
        centroids_by_vintage["v2010"] = linkage.centroids_2010
    if linkage.centroids_2000 is not None:
        centroids_by_vintage["v2000"] = linkage.centroids_2000
    return BlockGeometry(centroids_by_vintage=centroids_by_vintage)


# --- API ---


def build_blocks(
    plans: list[Plan],
    state: SupportedStateCode,
    chamber: SupportedChamberType,
    scope: ScopeSettings,
    project_paths: ProjectPaths,
    census_source: CensusSource,
    block_assignments: list[BlockAssignmentEntry],
    lewis_landing_url: str,
    output_path: Path,
    allow_missing: bool = False,
    spatial_join_fallback: bool = False,
) -> BlocksBuildResult:
    """Build the per-state block-lookup JSON for one state."""
    build_plan: _BuildPlan = _validate_inputs(
        plans=plans,
        state=state,
        scope=scope,
        project_paths=project_paths,
        census_source=census_source,
        block_assignments=block_assignments,
        allow_missing=allow_missing,
        spatial_join_fallback=spatial_join_fallback,
        lewis_landing_url=lewis_landing_url,
    )

    needs_2010_linkage, needs_2000_linkage = _classify_linkage_needs(build_plan)
    linkage: _BlockLinkage = _build_block_linkage(
        build_plan,
        needs_2010_linkage=needs_2010_linkage,
        needs_2000_linkage=needs_2000_linkage,
    )
    geometry: BlockGeometry = _build_block_geometry(linkage)
    assignments: dict[int, dict[str, int]] = _load_assignments(build_plan, geometry)

    histories_by_block: dict[str, list[int | None]] = _build_block_histories(
        build_plan=build_plan, linkage=linkage, assignments=assignments
    )
    blocks_map, unique_histories = _deduplicate_histories(histories_by_block)

    write_json_atomic(
        output_path,
        {
            "schema_version": _OUTPUT_SCHEMA_VERSION,
            "state": state,
            "chamber": chamber,
            "congress_start": scope.congress_start,
            "congress_end": scope.congress_end,
            "congresses": _serialize_congresses(build_plan),
            "histories": unique_histories,
            "blocks": blocks_map,
        },
    )

    unsourced_congresses: list[int] = sorted(
        congress
        for congress, source in build_plan.sources.items()
        if isinstance(source, UnsourcedSource)
    )

    return BlocksBuildResult(
        state=state,
        output_path=output_path,
        blocks_count=len(blocks_map),
        histories_count=len(unique_histories),
        unsourced_congresses=unsourced_congresses,
        warnings=(
            linkage.warnings
            + build_plan.resolution_warnings
            + [_summarize_linkage(linkage)]
        ),
    )


# --- Stages ---


def _build_block_linkage(
    build_plan: _BuildPlan, *, needs_2010_linkage: bool, needs_2000_linkage: bool
) -> _BlockLinkage:
    """Load 2020 block centroids and build cross-decade linkages on demand.

    The chain extends only as deep as the sourcing matrix requires:
        - Neither flag set: load 2020 centroids only (no chain)
        - `needs_2010_linkage=True`: build 2020 → 2010 linkage
        - `needs_2000_linkage=True`: build 2020 → 2000 linkage
    """
    centroids_2020: dict[str, Centroid] = load_centroids(
        tabblock_path=build_plan.tabblock_paths["v2020"],
        columns=TABBLOCK_COLUMNS["v2020"],
        state_fips=build_plan.state_fips,
    )

    if not needs_2010_linkage and not needs_2000_linkage:
        return _BlockLinkage(
            centroids_2020=centroids_2020,
            centroids_2010=None,
            centroids_2000=None,
            linkage_2020_to_2010=None,
            linkage_2020_to_2000=None,
            warnings=[],
        )

    polys_2010, centroids_2010 = load_block_polygons(
        tabblock_path=build_plan.tabblock_paths["v2010"],
        columns=TABBLOCK_COLUMNS["v2010"],
        state_fips=build_plan.state_fips,
    )
    join_2020_to_2010: CrossDecadeResult = cross_decade_join(
        source_centroids=centroids_2020,
        target_polygons=polys_2010,
        target_geoid_col=TABBLOCK_COLUMNS["v2010"].geoid,
        target_centroids=centroids_2010,
    )
    del polys_2010

    warnings: list[str] = []
    dropped_at_2010: int = len(centroids_2020) - len(join_2020_to_2010.linkage)
    if dropped_at_2010 > 0:
        warnings.append(
            f"{dropped_at_2010} 2020 block(s) unmatched in 2020 → 2010 join"
        )

    if not needs_2000_linkage:
        return _BlockLinkage(
            centroids_2020=centroids_2020,
            centroids_2010=centroids_2010,
            centroids_2000=None,
            linkage_2020_to_2010=join_2020_to_2010.linkage,
            linkage_2020_to_2000=None,
            warnings=warnings,
        )

    polys_2000, centroids_2000 = load_block_polygons(
        tabblock_path=build_plan.tabblock_paths["v2000"],
        columns=TABBLOCK_COLUMNS["v2000"],
        state_fips=build_plan.state_fips,
    )
    join_2010_to_2000: CrossDecadeResult = cross_decade_join(
        source_centroids=join_2020_to_2010.target_centroids,
        target_polygons=polys_2000,
        target_geoid_col=TABBLOCK_COLUMNS["v2000"].geoid,
        target_centroids=centroids_2000,
    )
    del polys_2000

    linkage_2020_to_2000: dict[str, str] = _compose_chain(
        join_2020_to_2010.linkage, join_2010_to_2000.linkage
    )
    dropped_at_2000: int = len(join_2020_to_2010.linkage) - len(linkage_2020_to_2000)
    if dropped_at_2000 > 0:
        warnings.append(
            f"{dropped_at_2000} 2010 block(s) unmatched in 2010 → 2000 join"
        )

    return _BlockLinkage(
        centroids_2020=centroids_2020,
        centroids_2010=centroids_2010,
        centroids_2000=centroids_2000,
        linkage_2020_to_2010=(
            join_2020_to_2010.linkage if needs_2010_linkage else None
        ),
        linkage_2020_to_2000=linkage_2020_to_2000,
        warnings=warnings,
    )


def _compose_chain(
    map_a_to_b: dict[str, str], map_b_to_c: dict[str, str]
) -> dict[str, str]:
    """Compose two single-step linkages into a direct A → C lookup.

    Entries in `map_a_to_b` whose target is missing from `map_b_to_c` are
    dropped (the chain doesn't reach all the way through for them).
    """
    composed: dict[str, str] = {}
    for a, b in map_a_to_b.items():
        c: str | None = map_b_to_c.get(b)
        if c is not None:
            composed[a] = c
    return composed


def _serialize_congresses(build_plan: _BuildPlan) -> list[dict[str, Any]]:
    """Serialize per-Congress provenance for the block_lookup output.

    Each entry records the plan_id governing that Congress and the discriminated
    `block_source` payload from the source's provenance() method. The same payload
    if propagated up into the manifest file, so any change here is a frontent contract
    change.
    """
    entries: list[dict[str, Any]] = []
    scope: ScopeSettings = build_plan.scope
    for congress in range(scope.congress_start, scope.congress_end + 1):
        source: BlockAssignmentSource = build_plan.sources[congress]
        plan: Plan = build_plan.plan_by_congress[congress]
        entries.append(
            {
                "congress": congress,
                "plan_id": plan.plan_id,
                "block_source": source.provenance(),
            }
        )

    return entries


def _load_assignments(
    build_plan: _BuildPlan, geometry: BlockGeometry
) -> dict[int, dict[str, int]]:
    """Load block-to-district assignemnts for every Congress in scope.

    Polygon-join results are cached by geojson_path so a multi-Congress
    Lewis plan is spatial-joined exactly once and reused across every
    Congress it covers.
    """
    assignments: dict[int, dict[str, int]] = {}
    polygon_cache: dict[Path, dict[str, int]] = {}

    for congress, source in build_plan.sources.items():
        if isinstance(source, PolygonJoinSource):
            cached: dict[str, int] | None = polygon_cache.get(source.geojson_path)
            if cached is not None:
                assignments[congress] = cached
                continue
            result: dict[str, int] = source.load(geometry)
            polygon_cache[source.geojson_path] = result
            assignments[congress] = result
        else:
            assignments[congress] = source.load(geometry)

    return assignments


def _build_block_histories(
    build_plan: _BuildPlan,
    linkage: _BlockLinkage,
    assignments: dict[int, dict[str, int]],
) -> dict[str, list[int | None]]:
    """Build the per-block district-history array, one slot per Congress in scope."""
    scope: ScopeSettings = build_plan.scope
    congress_count: int = scope.congress_end - scope.congress_start + 1
    map_2010: dict[str, str] | None = linkage.linkage_2020_to_2010
    map_2000: dict[str, str] | None = linkage.linkage_2020_to_2000
    histories: dict[str, list[int | None]] = {}

    for geoid_2020 in linkage.centroids_2020:
        geoid_2010: str | None = map_2010.get(geoid_2020) if map_2010 else None
        geoid_2000: str | None = map_2000.get(geoid_2020) if map_2000 else None
        history: list[int | None] = [None] * congress_count

        for congress in range(scope.congress_start, scope.congress_end + 1):
            idx: int = congress - scope.congress_start
            history[idx] = _district_for_congress(
                congress=congress,
                build_plan=build_plan,
                geoid_2020=geoid_2020,
                geoid_2010=geoid_2010,
                geoid_2000=geoid_2000,
                assignments=assignments,
            )
        histories[geoid_2020] = history

    return histories


def _district_for_congress(
    congress: int,
    build_plan: _BuildPlan,
    geoid_2020: str,
    geoid_2010: str | None,
    geoid_2000: str | None,
    assignments: dict[int, dict[str, int]],
) -> int | None:
    """Resolve a single (block, congress) -> district lookup."""
    source: BlockAssignmentSource = build_plan.sources[congress]
    vintage: BlockVintage | None = source.block_vintage

    if vintage is None:
        return None

    geoid: str | None
    if vintage == "v2020":
        geoid = geoid_2020
    elif vintage == "v2010":
        geoid = geoid_2010
    elif vintage == "v2000":
        geoid = geoid_2000

    if geoid is None:
        return None
    return assignments[congress].get(geoid)


def _deduplicate_histories(
    histories_by_block: dict[str, list[int | None]],
) -> tuple[dict[str, int], list[list[int | None]]]:
    """Collapse identical per-block histories into a shared index.

    Returns `(blocks_map, unique_histories)` where `blocks_map[geoid]` is an
    index into `unique_histories`. Iteration over `histories_by_block` is sorted
    by GEOID so output is deterministic.
    """
    history_to_index: dict[tuple[int | None, ...], int] = {}
    unique_histories: list[list[int | None]] = []
    blocks_map: dict[str, int] = {}

    for geoid, history in sorted(histories_by_block.items()):
        key: tuple[int | None, ...] = tuple(history)
        if key not in history_to_index:
            history_to_index[key] = len(unique_histories)
            unique_histories.append(history)
        blocks_map[geoid] = history_to_index[key]

    return blocks_map, unique_histories
