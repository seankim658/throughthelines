"""Explicit-hole block-assignment source."""

from __future__ import annotations
from dataclasses import dataclass

from pipeline.config import BlockVintage
from pipeline.blocks.sources.base import BlockAssignmentSource, BlockGeometry
from pipeline.blocks.sources.provenance import UnsourcedProvenance


@dataclass(frozen=True)
class UnsourcedSource(BlockAssignmentSource):
    """A Congress with no available block-to-district source."""

    # --- Contract ---

    @property
    def block_vintage(self) -> BlockVintage | None:
        return None

    def load(self, geometry: BlockGeometry) -> dict[str, int]:
        del geometry
        return {}

    def provenance(self) -> UnsourcedProvenance:
        return UnsourcedProvenance(
            type="unsourced",
        )
