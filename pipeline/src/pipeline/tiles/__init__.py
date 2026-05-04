"""Tiles module.

Builds per-state PMTiles archives from the stitched GeoJSON via
the `tippecanoe` CLI. Output is consumed at runtime by MapLibre
GL JS in the SvelteKit frontend.
"""

from pipeline.tiles.build import TilesBuildError, TilesBuildResult, build_tiles

__all__ = ["TilesBuildError", "TilesBuildResult", "build_tiles"]
