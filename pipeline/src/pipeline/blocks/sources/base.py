"""Block-assignemnt source contract.

A BlockAssignmentSource maps Census blocks to districts for one plan, keyed in one decade's block
geometry. The builder owns cross-decade linkage and the {congress -> source} mapping.

Concrete sources live in sibling modules:
    - delimited.py:     CSV/TSV block-assignment files
                        (Census BEFs, NC General Assembly BAF, ...)
    - polygon_join.py:  block centroids spatially joined against plan polygons
                        (Lewis archive)
    - unsourced:        explicit "no source available" placeholder

To add a new source type:

    1. Create a module in this submodule
    2. Subclass BlockAssignmentSource
    3. Implement the three abstract methods:
        block_vintage:  which decade's block GEOIDs your keys use
        load:           returns {block_geoid: district}
        provenance:     describes the source for downstream consumers
    4. Re-export the class from this submodule's __init__.py
    5. Wire its construction into blocks/build.py's source resolution

Design rules:

    - A source knows its upstream format and its block vintage. It does not know its plan_id
    of which Congress it serves, that's the responsibility of the builder. This keeps sources
    reusable across Congresses if a single upstream covers a multi-Congress plan.
    - `load()` is the only point where any I/O happens. Constructors should validate things such
    as the file existing, the required config is present, etc.
    - The `provenance()` shape is part of the frontend contract
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass

from pipeline.blocks.readers import Centroid
from pipeline.blocks.sources.provenance import BlockSourceProvenance
from pipeline.config import BlockVintage


@dataclass(frozen=True)
class BlockGeometry:
    """Per-decade Census block centroids, loaded once and shared across sources.

    The builder loads only the vintages actually required by the active
    sources (declared via `BlockAssignmentSource.block_vintage`) and passes
    this accessor to each source's `load()` call.

    Sources that read pre-computed assignment files ignore the accessor.
    Sources that derive assignments from plan polygons request the centroids
    of their declared vintage.
    """

    centroids_by_vintage: dict[BlockVintage, dict[str, Centroid]]

    def centroids(self, vintage: BlockVintage) -> dict[str, Centroid]:
        """Return {block_geoid: Centroid} for the given vintage."""
        if vintage not in self.centroids_by_vintage:
            raise KeyError(
                f"centroids for vintage {vintage!r} were not loaded; "
                f"a source declared this vintage but the builder did not "
                f"include it in the linkage stage. Loaded vintages: "
                f"{sorted(self.centroids_by_vintage.keys())}"
            )
        return self.centroids_by_vintage[vintage]


class BlockAssignmentSource(ABC):
    """One plan's block-to-district assignment, keyed in one decade's blocks."""

    @property
    @abstractmethod
    def block_vintage(self) -> BlockVintage | None:
        """Which decade's block GEOIDs this source's keys belong to."""

    @abstractmethod
    def load(self, geometry: BlockGeometry) -> dict[str, int]:
        """Return {block_geoid: district} keyed in `self.block_vintage`.

        Sources that read pre-computed assignment files ignore `geometry`.
        Sources that derive assignments from plan polygons pull centroids
        of their declared vintage from `geometry`.

        Returning an empty dict is valid (unsourced).
        """

    @abstractmethod
    def provenance(self) -> BlockSourceProvenance:
        """Return the `block_source` payload for the serialized output.

        The return type is a discriminated union of TypedDicts, one
        variant per source class, tagged by the `type` field. See
        `pipeline.blocks.sources.provenance` for the union definition,
        the per-variant shapes, and the recipe for adding a new variant
        when you add a new source class.

        The dict this returns lands verbatim under
        `congresses[i].block_source` in the serialized block-lookup
        output, so its shape is part of the frontend contract.
        """
