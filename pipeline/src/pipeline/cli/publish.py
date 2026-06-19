from __future__ import annotations

import sys

from pydantic import ValidationError
from pydantic_core import ErrorDetails

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
        )
    except PublishError as e:
        print(f"publish failed: {e}", file=sys.stderr)
        return 1

    if result.url_prefix is None:
        print(
            "\twarn: manifest has a null url_prefix; versioned artifacts were "
            "uploaded without a v/<sha> prefix. Set THROUGH_THE_LINES_GIT_SHA "
            "and rebuild the manifest for a versioned deploy.",
            file=sys.stderr,
        )

    for action, key in result.outcomes:
        print(f"\t{action:8} {key}")

    mb: float = result.total_bytes / (1024 * 1024)
    print(
        f"\n{result.uploaded} uploaded, {result.skipped} skipped "
        f"({mb:.1f} MB) → {result.bucket}"
    )
    print(f"manifest → {result.manifest_key} (atomic pointer, written last)")
    return 0


def _env_var_name(error: ErrorDetails) -> str:
    field = str(error["loc"][0])
    prefix = R2Settings.model_config.get("env_prefix", "")
    return f"{prefix}{field}".upper()
