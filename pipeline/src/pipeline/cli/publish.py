from __future__ import annotations

import sys

from pydantic import ValidationError
from pydantic_core import ErrorDetails

from pipeline.cli._common import format_bytes
from pipeline.config import ProjectConfig
from pipeline.publish import PublishError, PublishResult, R2Settings, publish_artifacts


def run_publish(project_config: ProjectConfig) -> int:
    paths = project_config.project_paths

    try:
        settings = R2Settings()  # pyright: ignore[reportCallIssue]
    except ValidationError as e:
        names = ", ".join(_env_var_name(err) for err in e.errors())
        print(
            f"error: missing or invalid environment variables: {names}", file=sys.stderr
        )
        return 2

    try:
        result: PublishResult = publish_artifacts(
            manifest_file=paths.manifest_file,
            derived_dir=paths.derived_dir,
            basemap_file=paths.basemap_file,
            settings=settings,
            publish_states=project_config.scope.publish,
        )
    except PublishError as e:
        print(f"publish failed: {e}", file=sys.stderr)
        return 1

    for action, key in result.outcomes:
        print(f"\t{action:8} {key}")

    print(
        f"\n{result.uploaded} uploaded, {result.skipped} skipped "
        f"({format_bytes(result.total_bytes)}) → {result.bucket}"
    )
    print(f"manifest → {result.manifest_key} (atomic pointer, written last)")
    return 0


def _env_var_name(error: ErrorDetails) -> str:
    field = str(error["loc"][0])
    prefix = R2Settings.model_config.get("env_prefix", "")
    return f"{prefix}{field}".upper()
