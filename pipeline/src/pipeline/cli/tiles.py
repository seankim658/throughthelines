from __future__ import annotations
import argparse
import shutil
import sys

from pipeline.cli._common import resolve_target_states
from pipeline.config import ProjectConfig, load_fetch_config
from pipeline.core import StateCode
from pipeline.tiles import TilesBuildError, TilesBuildResult, build_tiles


def run_tiles(project_config: ProjectConfig, args: argparse.Namespace) -> int:
    states_arg: list[StateCode] | None = args.state

    if shutil.which("tippecanoe") is None:
        print(
            "error: `tippecanoe` not found on $PATH; install the Felt fork "
            "from https://github.com/felt/tippecanoe/releases",
            file=sys.stderr,
        )
        return 2

    try:
        sources = load_fetch_config(project_config.sources_config_path)
    except (OSError, ValueError) as e:
        print(f"error loading config: {e}", file=sys.stderr)
        return 2

    target_states, error = resolve_target_states(states_arg, sources.lewis.states)
    if error is not None:
        print(f"error: {error}", file=sys.stderr)
        return 2
    assert target_states is not None

    paths = project_config.project_paths
    failed: bool = False
    succeeded: int = 0

    for state in target_states:
        print(f"\n[{state}]")
        stitched_path = paths.stitched_dir / f"{state}.geojson"
        try:
            result: TilesBuildResult = build_tiles(
                state=state, stitched_path=stitched_path, tiles_dir=paths.tiles_dir
            )
        except TilesBuildError as e:
            print(f"\ttiles failed: {e}", file=sys.stderr)
            failed = True
            continue

        print(f"\t→ {result.output_path} ({_format_bytes(result.file_size_bytes)})")
        succeeded += 1

    print(f"\n{succeeded} state(s) tiled.")

    return 1 if failed else 0


def _format_bytes(n: int) -> str:
    if n < 1024:
        return f"{n} B"
    if n < 1024 * 1024:
        return f"{n / 1024:.1f} KB"
    return f"{n / (1024 * 1024):.1f} MB"
