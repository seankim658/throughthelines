from __future__ import annotations

import re
from pathlib import Path

import pytest

from pipeline.config import ProjectConfigError, load_project_config, published_scope


def _write_project(tmp_path: Path, repo_root: Path, publish_line: str) -> Path:
    """Copy the shipped project.toml with its publish line replaced.

    An empty `publish_line` removes the key.
    """
    shipped: str = (repo_root / "config" / "project.toml").read_text("utf-8")
    replaced, count = re.subn(r"(?m)^publish = .*$\n?", publish_line, shipped)
    assert count == 1
    path: Path = tmp_path / "project.toml"
    path.write_text(replaced, encoding="utf-8")
    return path


def test_publish_lists_states_ready_to_go_live(tmp_path: Path, repo_root: Path) -> None:
    path: Path = _write_project(tmp_path, repo_root, 'publish = ["VA", "NC"]\n')

    scope = load_project_config(path, repo_root=str(repo_root)).scope

    assert scope.publish == ["VA", "NC"]
    assert set(scope.publish) < set(scope.chambers)


def test_empty_publish_list_is_allowed(tmp_path: Path, repo_root: Path) -> None:
    path: Path = _write_project(tmp_path, repo_root, "publish = []\n")

    scope = load_project_config(path, repo_root=str(repo_root)).scope

    assert scope.publish == []


def test_missing_publish_key_is_rejected(tmp_path: Path, repo_root: Path) -> None:
    path: Path = _write_project(tmp_path, repo_root, "")

    with pytest.raises(ProjectConfigError, match=r"scope\.publish is required"):
        load_project_config(path, repo_root=str(repo_root))


def test_publish_state_must_be_built(tmp_path: Path, repo_root: Path) -> None:
    path: Path = _write_project(tmp_path, repo_root, 'publish = ["NC", "CA"]\n')

    with pytest.raises(ProjectConfigError, match=r"'CA' .* not in scope\.chambers"):
        load_project_config(path, repo_root=str(repo_root))


def test_publish_rejects_a_repeated_state(tmp_path: Path, repo_root: Path) -> None:
    path: Path = _write_project(tmp_path, repo_root, 'publish = ["NC", "NC"]\n')

    with pytest.raises(ProjectConfigError, match="'NC' more than once"):
        load_project_config(path, repo_root=str(repo_root))


def test_publish_must_be_a_list(tmp_path: Path, repo_root: Path) -> None:
    path: Path = _write_project(tmp_path, repo_root, 'publish = "NC"\n')

    with pytest.raises(ProjectConfigError, match=r"scope\.publish must be a list"):
        load_project_config(path, repo_root=str(repo_root))


def test_published_scope_keeps_only_published_states(repo_root: Path) -> None:
    scope = load_project_config(
        repo_root / "config" / "project.toml", repo_root=str(repo_root)
    ).scope

    narrowed = published_scope(scope)

    assert sorted(narrowed.chambers) == sorted(scope.publish)
    assert narrowed.publish == scope.publish
    assert narrowed.congress_start == scope.congress_start
    assert narrowed.congress_end == scope.congress_end


def test_published_scope_lists_unpublished_built_states_as_planned(
    repo_root: Path,
) -> None:
    scope = load_project_config(
        repo_root / "config" / "project.toml", repo_root=str(repo_root)
    ).scope
    unpublished: list[str] = sorted(set(scope.chambers) - set(scope.publish))

    narrowed = published_scope(scope)

    assert unpublished
    assert narrowed.planned == [*scope.planned, *unpublished]
