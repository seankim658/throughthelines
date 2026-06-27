from __future__ import annotations
import sys

from pipeline.cli._common import (
    CliError,
    load_sources,
    print_warnings,
    print_warning_count,
)
from pipeline.config import ProjectConfig
from pipeline.manifest import ManifestBuildError, ManifestBuildResult, build_manifest


def run_manifest(project_config: ProjectConfig) -> int:
    paths = project_config.project_paths

    try:
        sources = load_sources(project_config)
    except CliError as e:
        print(str(e), file=sys.stderr)
        return 2

    try:
        result: ManifestBuildResult = build_manifest(
            project_config=project_config,
            sources=sources,
            output_path=paths.manifest_file,
        )
    except ManifestBuildError as e:
        print(f"manifest build failed: {e}", file=sys.stderr)
        return 1

    print_warnings(result.warnings)

    for state in sorted(project_config.scope.chambers.keys()):
        chambers = project_config.scope.chambers[state]
        chamber_label: str = ", ".join(chambers)
        print(f"\n[{state}]")
        print(f"\t[{chamber_label}] block_lookup, tiles → manifest")

    sha_label: str = result.git_sha if result.git_sha is not None else "null"
    prefix_label: str = result.url_prefix if result.url_prefix is not None else "null"

    print(
        f"\n{result.states_count} state(s), {result.chambers_count} chamber(s), "
        f"{result.total_artifacts} artifact(s) → {result.output_path}"
    )
    print(
        f"build: v{result.version} ({sha_label}) at {result.built_at} "
        f"(url_prefix: {prefix_label})"
    )

    print_warning_count(len(result.warnings))

    return 0
