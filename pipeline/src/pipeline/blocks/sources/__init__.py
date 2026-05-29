"""Block-assignment sources.

See `base.py` for the contract and the convention for adding new sources.
"""

from pipeline.blocks.sources.base import BlockAssignmentSource, BlockGeometry
from pipeline.blocks.sources.delimited import DelimitedAssignmentSource
from pipeline.blocks.sources.polygon_join import PolygonJoinSource
from pipeline.blocks.sources.unsourced import UnsourcedSource
from pipeline.blocks.sources.provenance import (
    BlockSourceProvenance,
    DelimitedAssignmentProvenance,
    PolygonJoinProvenance,
    UnsourcedProvenance,
)

__all__ = [
    "BlockAssignmentSource",
    "BlockGeometry",
    "BlockSourceProvenance",
    "DelimitedAssignmentProvenance",
    "DelimitedAssignmentSource",
    "PolygonJoinProvenance",
    "PolygonJoinSource",
    "UnsourcedProvenance",
    "UnsourcedSource",
]
