"""Provenance payloads for block-assignment sources.

A `BlockAssignmentSource.provenance()` call returns one of the TypedDicts
defined here. THe union is a discriminated union tagged on the `type` field.
Downstream readers (the serialized block-lookup JSON, the frontend, the manifest)
switch on `type` to read the variant-specific keys.

The shape of these payloads is part of the frontend contract: the dict a source
returns lands under `congresses[i].block_source` in `block_lookup_{STATE}_{CHAMBER}.json`.
Changing a key name, removing a field, or adding a required field is a breaking change
for any consumer of that file. Add fields cautiously and coordinate with the frontend.

To add a new source type:

    1. Define a new TypedDict variant below, with `type: Literal["..."]` as the
       discriminator. The literal value should be the snake_case name of the source
       class.
    2. Include `block_vintage` and `provider` so the variant has the same sahred fields
       the existing variants do (kept explicit per variant rather than inherited).
    3. Add the new variant to the `BlockSourceProvenance` union at the bottom of the file.
    4. Re-export the new variant from `sources/__init__.py`.
"""

from __future__ import annotations
from typing import Literal, TypedDict

from pipeline.config import BlockVintage


class DelimitedAssignmentProvenance(TypedDict):
    """Provenance for a CSV/TSV block-assignment file."""

    type: Literal["delimited_assignment"]
    block_vintage: BlockVintage
    provider: str  # short label, e.g. "census", "ncga"
    inner_filename: str  # the assignment file inside the upstream zip
    upstream_url: str  # the zip's URL
    upstream_landing_url: str  # human-readable landing page for the zip


class PolygonJoinProvenance(TypedDict):
    """Provenance for an assignment derived by joining block centroids to plan polygons."""

    type: Literal["polygon_join"]
    block_vintage: BlockVintage
    provider: str  # short label, e.g. "lewis", "ncga"
    source_file: str  # repo-relative path to the polygon file
    upstream_landing_url: str  # human-readable landing page for the polygon source


class UnsourcedProvenance(TypedDict):
    """Provenance for a Congress with no available block-to-district source."""

    type: Literal["unsourced"]


BlockSourceProvenance = (
    DelimitedAssignmentProvenance | PolygonJoinProvenance | UnsourcedProvenance
)
