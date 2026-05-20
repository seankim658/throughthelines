"""Build PMTiles archives from stitched GeoJSON via tippecanoe.

Per-state shell-out to the `tippecanoe` CLI (Felt fork). The
stitched GeoJSONs for one state (one file per output tile-layer)
are converted into a single `.pmtiles` file containing one vector-tile
layer per input.

External dependency: `tippecanoe` must be on $PATH at build time.
"""

from __future__ import annotations
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from pipeline.core import SupportedStateCode, SupportedChamberType, replace_atomic

# Name of the binary to shell out to
_TIPPECANOE_BIN: str = "tippecanoe"

# --- Errors ---


class TilesBuildError(Exception):
    """Raised when tile generation cannot complete for a state."""


# --- Models ---


@dataclass(frozen=True)
class TilesBuildResult:

    state: SupportedStateCode
    output_path: Path
    file_size_bytes: int


# --- API ---


def build_tiles(
    state: SupportedStateCode,
    chamber: SupportedChamberType,
    layer_inputs: dict[str, Path],
    tiles_dir: Path,
) -> TilesBuildResult:
    """Build one state's PMTiles file from per-layer stitched GeoJSONs.

    Each entry in `layer_inputs` becomes one tippecanoe `-L name:file`
    argument, producing an independent vector-tile layer of that name
    in the output PMTiles archive.
    """
    if shutil.which(_TIPPECANOE_BIN) is None:
        raise TilesBuildError(
            f"`{_TIPPECANOE_BIN}` not found on $PATH; install the Felt fork "
            f"from https://github.com/felt/tippecanoe/releases"
        )

    if not layer_inputs:
        raise TilesBuildError(f"no layer inputs provided for state {state}")

    for layer_name, path in layer_inputs.items():
        if not path.exists():
            raise TilesBuildError(
                f"stitched GeoJSON for layer {layer_name!r} not found at {path} "
                f"(did you run `pipeline stitch --state {state}`?)"
            )

    tiles_dir.mkdir(parents=True, exist_ok=True)
    output_path: Path = tiles_dir / f"{state}_{chamber}.pmtiles"
    tmp_path: Path = output_path.with_name(f".{output_path.stem}.partial.pmtiles")

    args: list[str] = [
        _TIPPECANOE_BIN,
        "-o",
        str(tmp_path),
        "-zg",
        "-r1",
        "--cluster-distance=0",
        "--no-feature-limit",
        "--no-tile-size-limit",
        "--no-tile-compression",
        "--force",
    ]
    for layer_name, path in layer_inputs.items():
        args.extend(["-L", f"{layer_name}:{path}"])

    completed: subprocess.CompletedProcess[str] = subprocess.run(
        args, capture_output=True, text=True, check=False
    )

    if completed.returncode != 0:
        if tmp_path.exists():
            tmp_path.unlink()
        raise TilesBuildError(
            f"tippecanoe exited with code {completed.returncode} for state {state}: "
            f"{completed.stderr.strip()}"
        )

    if not tmp_path.exists() or tmp_path.stat().st_size == 0:
        raise TilesBuildError(
            f"tippecanoe completed for {state} but produced no output at {tmp_path}"
        )

    replace_atomic(tmp_path, output_path)

    return TilesBuildResult(
        state=state, output_path=output_path, file_size_bytes=output_path.stat().st_size
    )
