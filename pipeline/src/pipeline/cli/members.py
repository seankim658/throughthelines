from __future__ import annotations
import sys
from pathlib import Path

from pipeline.config import ProjectConfig
from pipeline.members import MembersBuildError, MembersBuildResult, build_members


def run_members(project_config: ProjectConfig) -> int:
    paths = project_config.project_paths
    voteview_csv_path: Path = paths.voteview_dir / "HSall_members.csv"

    try:
        result: MembersBuildResult = build_members(
            scope=project_config.scope,
            voteview_csv_path=voteview_csv_path,
            output_path=paths.members_file,
        )
    except MembersBuildError as e:
        print(f"members build failed: {e}", file=sys.stderr)
        return 1

    for warning in result.warnings:
        print(f"\twarn: {warning}", file=sys.stderr)

    print(
        f"\n{result.rows_read} rows read, {result.rows_in_scope} in scope, "
        f"{result.districts_covered} (state, congress, district) entries "
        f"→ {result.output_path}"
    )
    if result.warnings:
        print(f"({len(result.warnings)} warning(s))", file=sys.stderr)

    return 0
