from __future__ import annotations
import sys

from pipeline.config import ProjectConfig, load_fetch_config, load_request_config
from pipeline.fetch import FetchError, fetch_all


def run_fetch(project_config: ProjectConfig) -> int:
    try:
        sources = load_fetch_config(project_config.sources_config_path)
        request = load_request_config(project_config.request_config_path)
    except (OSError, ValueError) as e:
        print(f"fetch failed: {e}", file=sys.stderr)
        return 2

    try:
        result = fetch_all(
            sources=sources,
            request_settings=request.request_settings,
            user_agent=project_config.user_agent,
            project_paths=project_config.project_paths,
        )
    except FetchError as e:
        print(f"fetch failed: {e}", file=sys.stderr)
        return 1

    fetched_count: int = sum(1 for f in result.files if f.status == "fetched")
    unchanged_count: int = sum(1 for f in result.files if f.status == "unchanged")

    for entry in result.files:
        marker: str = "->" if entry.status == "fetched" else "."
        print(f"\t{marker} {entry.status:9s} {entry.source_url}")

    print(
        f"\n{fetched_count} fetched, {unchanged_count} unchanged. "
        f"manifest: {result.manifest_path}"
    )
    return 0
