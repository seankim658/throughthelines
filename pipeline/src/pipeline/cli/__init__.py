from __future__ import annotations
import argparse
import sys
from pathlib import Path

from pipeline.cli._common import validate_state
from pipeline.config import load_project_config, ProjectConfigError
from pipeline.core import RepoRootNotFoundError, find_repo_root


def main(argv: list[str] | None = None) -> int:
    parser: argparse.ArgumentParser = _build_parser()
    args: argparse.Namespace = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 1

    try:
        repo_root: Path = find_repo_root()
    except RepoRootNotFoundError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    project_config_path: Path = repo_root / "config" / "project.toml"
    try:
        project_config = load_project_config(project_config_path, str(repo_root))
    except ProjectConfigError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    if args.command == "fetch":
        from pipeline.cli.fetch import run_fetch

        return run_fetch(project_config)

    if args.command == "scaffold-plans":
        from pipeline.cli.scaffold import run_scaffold

        return run_scaffold(project_config, args)

    if args.command == "normalize-geometry":
        from pipeline.cli.geometry import run_normalize_geometry

        return run_normalize_geometry(project_config, args)

    if args.command == "stitch":
        from pipeline.cli.stitch import run_stitch

        return run_stitch(project_config, args)

    if args.command == "members":
        from pipeline.cli.members import run_members

        return run_members(project_config)

    if args.command == "blocks":
        from pipeline.cli.blocks import run_blocks

        return run_blocks(project_config, args)

    if args.command == "tiles":
        from pipeline.cli.tiles import run_tiles

        return run_tiles(project_config, args)

    if args.command == "basemap":
        from pipeline.cli.basemap import run_basemap

        return run_basemap(project_config, args)

    if args.command == "plan-index":
        from pipeline.cli.plan_index import run_plan_index

        return run_plan_index(project_config)

    if args.command == "manifest":
        from pipeline.cli.manifest import run_manifest

        return run_manifest(project_config)

    if args.command == "publish":
        from pipeline.cli.publish import run_publish

        return run_publish(project_config)

    parser.print_help()
    return 1


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pipeline",
        description="Build pipeline",
        epilog=(
            "Recommended run order:\n"
            "  1. fetch                 Download upstream sources (except the basemap)\n"
            "  2. scaffold-plans        Generate placeholder plan-metadata YAMLs\n"
            "  3. normalize-geometry    Normalize non-Lewis shapefiles into GeoJSON\n"
            "  3. stitch                Stitch plan metadata onto district polygons\n"
            "  4. members               Slice Voteview into per-state members.json\n"
            "  5. blocks                Build per-state block-lookup JSON\n"
            "  6. tiles                 Build PMTiles archives via tippecanoe\n"
            "  7. basemap               Extract CONUS basemap via pmtiles CLI\n"
            "  8. plan-index            Build plan_index.json for the frontend\n"
            "  9. manifest              Build manifest.json (run last)\n"
            " 10. publish               Upload artifacts to R2 (deploy; needs R2_* env)\n"
            "\n"
            "Steps 5-9 are independent and can run in any order after step 4.\n"
            "Step 11 (publish) requires a built manifest and R2 credentials."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", metavar="COMMAND")

    # Fetch
    subparsers.add_parser("fetch", help="Download upstream sources to data/raw/.")

    # Scaffold
    scaffold_parser = subparsers.add_parser(
        "scaffold-plans",
        help="Generate placeholder plan-metadata YAMLs from Lewis GeoJSONs.",
    )
    _add_state_argument(scaffold_parser, "scaffold")
    scaffold_parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing YAMLs. Off by default.",
    )
    scaffold_parser.add_argument(
        "patterns",
        nargs="*",
        metavar="PATTERN",
        help=(
            "Optional glob patterns matched against Lewis filenames "
            "(e.g., '*119*'). Multiple patterns are OR-combined. "
            "If omitted, all files are processed."
        ),
    )

    # Normalize geometry
    normalize_geometry_parser = subparsers.add_parser(
        "normalize-geometry",
        help=(
            "Normalize fetched district shapefiles into WGS84 GeoJSON "
            "(non-Lewis geometry sources). Run after fetch, before stitch."
        ),
    )
    _add_state_argument(normalize_geometry_parser, "normalize")

    # Stitch
    stitch_parser = subparsers.add_parser(
        "stitch",
        help="Stitch plan metadata onto district polygons; emit per-state GeoJSON.",
    )
    _add_state_argument(stitch_parser, "stitch")

    # Members
    subparsers.add_parser("members", help="Slice Voteview CSV into members.json.")

    # Blocks
    blocks_parser = subparsers.add_parser(
        "blocks",
        help="Build per-state block-lookup JSON for the address-lookup pipeline.",
    )
    _add_state_argument(blocks_parser, "build")
    blocks_parser.add_argument(
        "--allow-missing",
        action="store_true",
        help=(
            "Fill Congresses with no available BEF or spatial-join source "
            "with JSON null instead of aborting. Off by default."
        ),
    )
    blocks_parser.add_argument(
        "--spatial-join-fallback",
        action="store_true",
        help=(
            "When a Congress in the BEF era (113+) has no [[block_assignment]] "
            "entry, fall back to a spatial join against its plan polygon if "
            "available. Off by default."
        ),
    )

    # Tiles
    tiles_parser = subparsers.add_parser(
        "tiles",
        help="Build per-state PMTiles archive from stitched GeoJSON via tippecanoe.",
    )
    _add_state_argument(tiles_parser, "tile")

    # Basemap
    basemap_parser = subparsers.add_parser(
        "basemap",
        help=(
            "Extract a CONUS basemap PMTiles archive from the pinned "
            "Protomaps daily build via the `pmtiles` CLI."
        ),
    )
    basemap_parser.add_argument(
        "--force",
        action="store_true",
        help="Bypass the cache check and re-extract.",
    )

    # Plan index
    subparsers.add_parser(
        "plan-index", help="Build plan_index.json metadata index for the frontend."
    )

    # Manifest
    subparsers.add_parser(
        "manifest",
        help=(
            "Build manifest.json, the frontend discovery document. " "Must be run last."
        ),
    )

    # Publish
    subparsers.add_parser(
        "publish",
        help=(
            "Upload derived artifacts to R2, writing manifest.json last. "
            "Run after manifest; requires R2_* credentials."
        ),
    )

    return parser


def _add_state_argument(parser: argparse.ArgumentParser, verb: str) -> None:
    parser.add_argument(
        "--state",
        action="append",
        type=validate_state,
        metavar="STATE",
        help=(
            f"Two-letter state code to {verb} (repeatable, e.g. "
            "--state NC --state PA). If omitted, applies to every state "
            "configured in sources.toml."
        ),
    )
