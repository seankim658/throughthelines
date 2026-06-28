from __future__ import annotations
import argparse
import shutil
import sys
from pathlib import Path

from pipeline.cli._common import (
    CliError,
    format_bytes,
    load_sources_and_states,
)
from pipeline.config import ProjectConfig
from pipeline.core import SupportedStateCode
from pipeline.tiles import TilesBuildError, TilesBuildResult, build_tiles


def run_tiles(project_config: ProjectConfig, args: argparse.Namespace) -> int:
    states_arg: list[SupportedStateCode] | None = args.state

    if shutil.which("tippecanoe") is None:
        print(
            "error: `tippecanoe` not found on $PATH; install the Felt fork "
            "from https://github.com/felt/tippecanoe/releases",
            file=sys.stderr,
        )
        return 2

    try:
        _, target_states = load_sources_and_states(project_config, states_arg)
    except CliError as e:
        print(str(e), file=sys.stderr)
        return 2

    paths = project_config.project_paths
    failed: bool = False
    succeeded: int = 0

    for state in target_states:
        print(f"\n[{state}]")
        # NOTE : stitched_path is per-state for now, will need to add chamber
        # dimension if state legislature gets added
        layer_inputs: dict[str, Path] = {
            "districts": paths.stitched_dir / f"{state}_districts.geojson",
            "labels": paths.stitched_dir / f"{state}_labels.geojson",
        }
        chambers = project_config.scope.chambers[state]
        for chamber in chambers:
            try:
                result: TilesBuildResult = build_tiles(
                    state=state,
                    chamber=chamber,
                    layer_inputs=layer_inputs,
                    tiles_dir=paths.tiles_dir,
                )
            except TilesBuildError as e:
                print(f"\t[{chamber}] tiles failed: {e}", file=sys.stderr)
                failed = True
                continue

            print(
                f"\t[{chamber}] → {result.output_path} "
                f"({format_bytes(result.file_size_bytes)})"
            )
            succeeded += 1

    print(f"\n{succeeded} state(s) tiled.")

    return 1 if failed else 0
