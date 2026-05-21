"""Build the CONUS basemap PMTiles archives via the `pmtiles` CLI.

Extracts a bounding-box subset from Protomaps' global daily basemap
build.

Cached via a sidecar stamp file (basemap.pmtiles.stamp.json) that
records the inputs used to produce the current output.

External dependency: `pmtiles` (go-pmtiles) must be on $PATH at build
time.
"""

from __future__ import annotations
import json
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from pipeline.core import replace_atomic

# Name of the go-pmtiles binary on $PATH
_PMTILES_BIN: str = "pmtiles"

_STAMP_SCHEMA_VERSION: int = 1

# --- Errors ---


class BasemapBuildError(Exception):
    """Raised when the basemap extract cannot complete."""


# --- Models ---


@dataclass(frozen=True)
class BasemapBuildResult:

    output_path: Path
    file_size_bytes: int
    cached: bool


@dataclass(frozen=True)
class _StampData:

    schema_version: int
    build_url: str
    bbox: tuple[float, float, float, float]
    max_zoom: int
    output_filename: str
    output_size_bytes: int


# --- API ---


def build_basemap(
    build_url: str,
    bbox: tuple[float, float, float, float],
    max_zoom: int,
    basemap_file: Path,
    force: bool = False,
) -> BasemapBuildResult:
    """Extract a bbox subset of a Promotomaps daily basemap build."""
    if shutil.which(_PMTILES_BIN) is None:
        raise BasemapBuildError(
            f"`{_PMTILES_BIN}` not found on $PATH; install go-pmtiles "
            f"from https://github.com/protomaps/go-pmtiles/releases"
        )

    if max_zoom < 0 or max_zoom > 15:
        raise BasemapBuildError(f"max_zoom must be between 0 and 15, got {max_zoom}")

    basemap_file.parent.mkdir(parents=True, exist_ok=True)
    output_path: Path = basemap_file
    stamp_path: Path = basemap_file.with_name(basemap_file.name + ".stamp.json")

    if not force and _is_cached(
        stamp_path=stamp_path,
        output_path=output_path,
        build_url=build_url,
        bbox=bbox,
        max_zoom=max_zoom,
    ):
        return BasemapBuildResult(
            output_path=output_path,
            file_size_bytes=output_path.stat().st_size,
            cached=True,
        )

    tmp_path: Path = output_path.with_name(f".{output_path.stem}.partial.pmtiles")
    if tmp_path.exists():
        tmp_path.unlink()

    west, south, east, north = bbox
    bbox_arg: str = f"{west},{south},{east},{north}"

    args: list[str] = [
        _PMTILES_BIN,
        "extract",
        build_url,
        str(tmp_path),
        f"--bbox={bbox_arg}",
        f"--maxzoom={max_zoom}",
    ]

    completed: subprocess.CompletedProcess[str] = subprocess.run(
        args, capture_output=True, text=True, check=False
    )

    if completed.returncode != 0:
        if tmp_path.exists():
            tmp_path.unlink()
        raise BasemapBuildError(
            f"pmtiles extract exited with code {completed.returncode}: "
            f"{completed.stderr.strip()}"
        )

    if not tmp_path.exists() or tmp_path.stat().st_size == 0:
        raise BasemapBuildError(
            f"pmtiles extract completed but produced no output at {tmp_path}"
        )

    replace_atomic(tmp_path, output_path)

    output_size: int = output_path.stat().st_size
    _write_stamp(
        stamp_path,
        build_url=build_url,
        bbox=bbox,
        max_zoom=max_zoom,
        output_filename=output_path.name,
        output_size_bytes=output_size,
    )

    return BasemapBuildResult(
        output_path=output_path, file_size_bytes=output_size, cached=False
    )


# --- Stamp file ---


def _is_cached(
    *,
    stamp_path: Path,
    output_path: Path,
    build_url: str,
    bbox: tuple[float, float, float, float],
    max_zoom: int,
) -> bool:
    if not stamp_path.exists() or not output_path.exists():
        return False
    try:
        stamp = _load_stamp(stamp_path)
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError):
        return False
    if stamp.schema_version != _STAMP_SCHEMA_VERSION:
        return False
    if stamp.build_url != build_url:
        return False
    if stamp.bbox != bbox:
        return False
    if stamp.max_zoom != max_zoom:
        return False
    if stamp.output_filename != output_path.name:
        return False
    if output_path.stat().st_size != stamp.output_size_bytes:
        return False
    return True


def _load_stamp(stamp_path: Path) -> _StampData:
    with stamp_path.open("r") as f:
        raw = json.load(f)
    if not isinstance(raw, dict):
        raise ValueError(f"stamp must be a JSON object, got {type(raw).__name__}")
    inputs = raw["inputs"]
    output = raw["output"]
    bbox_raw = inputs["bbox"]
    if not isinstance(bbox_raw, list) or len(bbox_raw) != 4:
        raise ValueError("stamp.inputs.bbox must be a 4-element list")
    return _StampData(
        schema_version=raw["schema_version"],
        build_url=inputs["build_url"],
        bbox=(
            float(bbox_raw[0]),
            float(bbox_raw[1]),
            float(bbox_raw[2]),
            float(bbox_raw[3]),
        ),
        max_zoom=inputs["max_zoom"],
        output_filename=output["filename"],
        output_size_bytes=output["size_bytes"],
    )


def _write_stamp(
    stamp_path: Path,
    *,
    build_url: str,
    bbox: tuple[float, float, float, float],
    max_zoom: int,
    output_filename: str,
    output_size_bytes: int,
) -> None:
    data: dict[str, object] = {
        "schema_version": _STAMP_SCHEMA_VERSION,
        "inputs": {
            "build_url": build_url,
            "bbox": list(bbox),
            "max_zoom": max_zoom,
        },
        "output": {
            "filename": output_filename,
            "size_bytes": output_size_bytes,
        },
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    tmp_path: Path = stamp_path.with_name(stamp_path.name + ".partial")
    with tmp_path.open("w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")
    replace_atomic(tmp_path, stamp_path)
