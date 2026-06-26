from __future__ import annotations
import shutil
import sys
from argparse import Namespace

from pipeline.cli._common import format_bytes
from pipeline.basemap import BasemapBuildError, BasemapBuildResult, build_basemap
from pipeline.config import ProjectConfig, load_fetch_config


def run_basemap(project_config: ProjectConfig, args: Namespace) -> int:
    if shutil.which("pmtiles") is None:
        print(
            "error: `pmtiles` not found on $PATH; install go-pmtiles "
            "from https://github.com/protomaps/go-pmtiles/releases",
            file=sys.stderr,
        )
        return 2

    try:
        sources = load_fetch_config(project_config.sources_config_path)
    except (OSError, ValueError) as e:
        print(f"error loading config: {e}", file=sys.stderr)
        return 2

    cfg = sources.protomaps_basemap

    print(f"[basemap]")
    print(f"\tbuild_url : {cfg.build_url}")
    print(f"\tbbox      : {cfg.bbox}")
    print(f"\tmaxzoom   : {cfg.max_zoom}")
    if args.force:
        print("\t--force  : cache bypassed")

    try:
        result: BasemapBuildResult = build_basemap(
            build_url=cfg.build_url,
            bbox=cfg.bbox,
            max_zoom=cfg.max_zoom,
            basemap_file=project_config.project_paths.basemap_file,
            force=args.force,
        )
    except BasemapBuildError as e:
        print(f"\tbasemap failed: {e}", file=sys.stderr)
        return 1

    status: str = "cached" if result.cached else "extracted"
    print(
        f"\t→ {result.output_path} "
        f"({format_bytes(result.file_size_bytes)}, {status})"
    )

    return 0
