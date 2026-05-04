"""Build PMTiles archives from stitched GeoJSON via tippecanoe.

Per-state shell-out to the `tippecanoe` CLI (Felt fork). The
stitched GeoJSON for one state is converted into a single
`.pmtiles` file.

External dependency: `tippecanoe` must be on $PATH at build time.
"""

from __future__ import annotations
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from pipeline.core import StateCode

# Name of the binary to shell out to
_TIPPECANOE_BIN: str = "tippecanoe"

# Vector tile name
_LAYER_NAME: str = "districts"

# --- Errors ---


class TilesBuildError(Exception):
    """Raised when tile generation cannot complete for a state."""


# --- Models ---


@dataclass(frozen=True)
class TilesBuildResult:

    state: StateCode
    output_path: Path
    file_size_bytes: int


# --- API ---


def build_tiles(
    state: StateCode, stitched_path: Path, tiles_dir: Path
) -> TilesBuildResult:
    """Build one state's PMTiles file from its stitched GeoJSON.

    Writes automatically: tippecanoe outputs to a `.tmp` sibling,
    which is renamed onto the final path only after a successful
    exit and a non-empty output check.
    """
    if shutil.which(_TIPPECANOE_BIN) is None:
        raise TilesBuildError(
            f"`{_TIPPECANOE_BIN}` not found on $PATH; install the Felt fork "
            f"from https://github.com/felt/tippecanoe/releases"
        )

    if not stitched_path.exists():
        raise TilesBuildError(
            f"stitched GeoJSON not found at {stitched_path} "
            f"(did you run `pipeline sticht --state {state}`?)"
        )

    tiles_dir.mkdir(parents=True, exist_ok=True)
    output_path: Path = tiles_dir / f"{state}.pmtiles"
    tmp_path: Path = output_path.with_suffix(output_path.suffix + ".tmp")

    args: list[str] = [
        _TIPPECANOE_BIN,
        "-o",
        str(tmp_path),
        "-zg",
        "--drop-densest-as-needed",
        "--extend-zooms-if-still-dropping",
        "--no-tile-compression",
        "-l",
        _LAYER_NAME,
        "--force",
        str(stitched_path),
    ]

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

    os.replace(tmp_path, output_path)

    return TilesBuildResult(
        state=state, output_path=output_path, file_size_bytes=output_path.stat().st_size
    )
