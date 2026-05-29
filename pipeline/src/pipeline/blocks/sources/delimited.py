"""Delimited block-assignment file source.

Covers any block-to-district mapping published as a CSV/TSV inside a zip:

    - Census Block Equivalency Files (BEFs), the standard Census product
      for the 113th Congress onward.
    - State-published block assignment files, e.g. NC General Assembly's
      Congress_2019 Blockfile (HB 1029 / SL 2019-249), which fills the
      117th-Congress gap.
"""

from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path

from pipeline.config import BlockVintage
from pipeline.blocks.readers import load_delimited_assignment
from pipeline.blocks.sources.base import BlockAssignmentSource, BlockGeometry
from pipeline.blocks.sources.provenance import DelimitedAssignmentProvenance


@dataclass(frozen=True)
class DelimitedAssignmentSource(BlockAssignmentSource):
    """A block-to-distrct assignment loaded from a delimited file in a zip."""

    # --- Config ---
    zip_path: Path
    inner_filename: str
    state_fips: str
    district_column: str
    _block_vintage: BlockVintage
    provider: str  # short label, e.g. "census", "ncga"
    upstream_url: str
    upstream_landing_url: str

    # Optional knobs; default match Census BEF conventions
    geoid_column: str | None = None  # None -> auto-detect {"BLOCKID", "GEOID"}
    delimiter: str = ","

    # --- Construction validation ---

    def __post_init__(self) -> None:
        if not self.zip_path.exists():
            raise FileNotFoundError(
                f"delimited-assignment zip not found at {self.zip_path} "
                f"(provider={self.provider!r}); did you run `pipeline fetch`?"
            )

    # --- Contract ---

    @property
    def block_vintage(self) -> BlockVintage:
        return self._block_vintage

    def load(self, geometry: BlockGeometry) -> dict[str, int]:
        # Geometry is unused for delimited sources
        del geometry
        return load_delimited_assignment(
            zip_path=self.zip_path,
            inner_filename=self.inner_filename,
            state_fips=self.state_fips,
            district_column=self.district_column,
            geoid_column=self.geoid_column,
            delimiter=self.delimiter,
        )

    def provenance(self) -> DelimitedAssignmentProvenance:
        return DelimitedAssignmentProvenance(
            type="delimited_assignment",
            block_vintage=self._block_vintage,
            provider=self.provider,
            inner_filename=self.inner_filename,
            upstream_url=self.upstream_url,
            upstream_landing_url=self.upstream_landing_url,
        )
