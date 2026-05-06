"""Manifest module.

Builds the manifest.json, the single discovery document the frontend
fetches first to find every other artifact.
"""

from pipeline.manifest.build import (
    ManifestBuildError,
    ManifestBuildResult,
    build_manifest,
)

__all__ = [
    "ManifestBuildError",
    "ManifestBuildResult",
    "build_manifest",
]
