from __future__ import annotations

import sys

from pipeline.config import ProjectConfig, load_fetch_config, load_request_config
from pipeline.fetch import (
    FetchError,
    FetchResult,
    HttpDownloader,
    fetch_national,
    fetch_state,
)


def run_fetch(project_config: ProjectConfig) -> int:
    try:
        sources = load_fetch_config(project_config.sources_config_path)
        request = load_request_config(project_config.request_config_path)
    except (OSError, ValueError) as e:
        print(f"fetch failed: {e}", file=sys.stderr)
        return 2

    downloader = HttpDownloader(request.request_settings, project_config.user_agent)
    paths = project_config.project_paths
    results: list[FetchResult] = []
    try:
        results.append(fetch_national(sources, paths, downloader))
        for state in sorted(project_config.scope.chambers):
            results.append(fetch_state(state, sources, paths, downloader))
    except FetchError as e:
        print(f"fetch failed: {e}", file=sys.stderr)
        return 1

    total_fetched: int = 0
    total_unchanged: int = 0
    for result in results:
        scope_label: str = "national" if result.state is None else result.state
        print(f"\n[{scope_label}]")
        for entry in result.files:
            marker: str = "→" if entry.status == "fetched" else "."
            print(f"\t{marker} {entry.status:9s} {entry.source_url}")
        total_fetched += sum(1 for f in result.files if f.status == "fetched")
        total_unchanged += sum(1 for f in result.files if f.status == "unchanged")
        print(f"\tfetch-state: {result.state_path}")

    print(
        f"\n{total_fetched} fetched, {total_unchanged} unchanged "
        f"across {len(results)} scopes."
    )
    return 0
