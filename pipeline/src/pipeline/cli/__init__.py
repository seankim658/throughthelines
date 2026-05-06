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

    if args.command == "plan-index":
        from pipeline.cli.plan_index import run_plan_index

        return run_plan_index(project_config)

    if args.command == "manifest":
        from pipeline.cli.manifest import run_manifest

        return run_manifest(project_config)

    parser.print_help()
    return 1


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pipeline", description="Build pipeline")
    subparsers = parser.add_subparsers(dest="command", metavar="COMMAND")

    # Fetch
    subparsers.add_parser("fetch", help="Download upstream sources to data/raw/.")

    # Scaffold
    scaffold_parser = subparsers.add_parser(
        "scaffold-plans",
        help="Generate placeholder plan-metadata YAMLs from Lewis GeoJSONs.",
    )
    scaffold_parser.add_argument(
        "--state",
        action="append",
        type=validate_state,
        metavar="STATE",
        help=(
            "Two-letter state code to scaffold (repeatable, e.g., "
            "--state NC --state PA). If omitted, scaffolds every state "
            "configured in sources.toml."
        ),
    )
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

    # Stitch
    stitch_parser = subparsers.add_parser(
        "stitch",
        help="Stitch plan metadata onto Lewis polygons; emit per-state GeoJSON.",
    )
    stitch_parser.add_argument(
        "--state",
        action="append",
        type=validate_state,
        metavar="STATE",
        help=(
            "Two-letter state code to stitch (repeatable). "
            "If omitted, stitches every state configured in sources.toml."
        ),
    )

    # Members
    subparsers.add_parser("members", help="Slice Voteview CSV into members.json.")

    # Blocks
    blocks_parser = subparsers.add_parser(
        "blocks",
        help="Build per-state block-lookup JSON for the address-lookup pipeline.",
    )
    blocks_parser.add_argument(
        "--state",
        action="append",
        type=validate_state,
        metavar="STATE",
        help=(
            "Two-letter state code to build (repeatable). "
            "If omitted, builds every state configured in sources.toml."
        ),
    )
    blocks_parser.add_argument(
        "--allow-missing",
        action="store_true",
        help=(
            "Fill Congresses with no available BEF or spatial-join source "
            "with JSON null instead of aborting. Off by default."
        ),
    )
    blocks_parser.add_argument(
        "--lewis-fallback",
        action="store_true",
        help=(
            "When a Congress in the BEF era (113+) has no BEF, fall back to "
            "a spatial join against its Lewis plan polygon if available."
        ),
    )

    # Tiles
    tiles_parser = subparsers.add_parser(
        "tiles",
        help="Build per-state PMTiles archive from stitched GeoJSON via tippecanoe.",
    )
    tiles_parser.add_argument(
        "--state",
        action="append",
        type=validate_state,
        metavar="STATE",
        help=(
            "Two-letter state code to file (repeatable). "
            "If omitted, tiles every state configured in sources.toml."
        ),
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

    return parser
