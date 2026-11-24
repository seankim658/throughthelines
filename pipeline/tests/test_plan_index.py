from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pipeline.config import load_fetch_config, load_project_config, published_scope
from pipeline.plans import build_plan_index


def _build_index(repo_root: Path, tmp_path: Path, *, published_only: bool) -> Any:
    config_dir: Path = repo_root / "config"
    scope = load_project_config(
        config_dir / "project.toml", repo_root=str(repo_root)
    ).scope
    sources = load_fetch_config(config_dir / "sources.toml")
    output_path: Path = tmp_path / "plan_index.json"
    build_plan_index(
        scope=published_scope(scope) if published_only else scope,
        plans_dir=repo_root / "data" / "plans",
        output_path=output_path,
        geometry_sources=sources.geometry_sources,
        lewis_homepage_url=sources.lewis.homepage,
    )
    return json.loads(output_path.read_text("utf-8")), scope


def test_published_index_holds_only_published_states(
    repo_root: Path, tmp_path: Path
) -> None:
    index, scope = _build_index(repo_root, tmp_path, published_only=True)

    assert sorted(index["plans"]) == sorted(scope.publish)


def test_full_index_holds_every_built_state_with_plans(
    repo_root: Path, tmp_path: Path
) -> None:
    index, scope = _build_index(repo_root, tmp_path, published_only=False)
    with_plans: set[str] = {
        state
        for state in scope.chambers
        if (repo_root / "data" / "plans" / state).is_dir()
    }

    assert set(index["plans"]) == with_plans
    assert with_plans - set(scope.publish)
