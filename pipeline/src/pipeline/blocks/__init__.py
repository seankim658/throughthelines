"""Blocks module.

Builds the per-state block-lookup JSON consumed by the frontend at
runtime to resolve a 2020 Census block GEOID into a per-Congress
district history.
"""

from pipeline.blocks.build import BlocksBuildError, BlocksBuildResult, build_blocks

__all__ = ["BlocksBuildError", "BlocksBuildResult", "build_blocks"]
