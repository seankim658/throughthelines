"""Locate repo root."""

from __future__ import annotations
from pathlib import Path


class RepoRootNotFoundError(Exception):
    """Raised when the repo root cannot be located."""


def find_repo_root(start: Path | None = None) -> Path:
    here: Path = (start or Path(__file__)).resolve()
    if here.is_file():
        here = here.parent

    for candidate in [here, *here.parents]:
        if (candidate / "config").is_dir() and (candidate / "pipeline").is_dir():
            return candidate

    raise RepoRootNotFoundError(
        f"could not find repo root walking up from {here} "
        f"(looking for a directory containing both 'config/' and 'pipeline/')"
    )
