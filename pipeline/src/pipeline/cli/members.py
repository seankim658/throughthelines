from __future__ import annotations

import argparse
import sys
from pathlib import Path

from pipeline.cli._common import (
    print_unpublished,
    print_warning_count,
    print_warnings,
    release_config,
)
from pipeline.config import ProjectConfig
from pipeline.members import MembersBuildError, MembersBuildResult, build_members


def run_members(project_config: ProjectConfig, args: argparse.Namespace) -> int:
    paths = project_config.project_paths
    release: ProjectConfig = release_config(project_config, args)
    voteview_csv_path: Path = paths.voteview_dir / "HSall_members.csv"

    try:
        result: MembersBuildResult = build_members(
            scope=release.scope,
            voteview_csv_path=voteview_csv_path,
            output_path=paths.members_file,
        )
    except MembersBuildError as e:
        print(f"members build failed: {e}", file=sys.stderr)
        return 1

    print_warnings(result.warnings)

    print(
        f"\n{result.rows_read} rows read, {result.rows_in_scope} in scope, "
        f"{result.districts_covered} (state, congress, district) entries "
        f"→ {result.output_path}"
    )
    print_unpublished(project_config, args)
    if result.warnings:
        print_warning_count(len(result.warnings))

    return 0
