from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest

from pipeline.publish import (
    PublishError,
    R2Settings,
    check_release_states,
    publish_artifacts,
)

PUBLISHED: list[str] = ["NC", "VA"]


def _write_release(
    derived_dir: Path,
    *,
    manifest_states: list[str],
    plan_states: list[str],
    member_states: list[str],
) -> dict[str, Any]:
    """Write a plan index and members file and return a manifest naming them."""
    derived_dir.mkdir(parents=True, exist_ok=True)
    plan_index: dict[str, Any] = {
        "schema_version": 1,
        "plans": {state: {} for state in plan_states},
    }
    members: dict[str, Any] = {state: {} for state in member_states}
    (derived_dir / "plan_index.json").write_text(json.dumps(plan_index), "utf-8")
    (derived_dir / "members.json").write_text(json.dumps(members), "utf-8")
    return {
        "build": {"url_prefix": "v/abc1234"},
        "artifacts": {
            "plan_index": {"path": "plan_index.json"},
            "members": {"path": "members.json"},
            "basemap": {"path": "basemap/basemap-0.pmtiles"},
        },
        "states": {state: {"chambers": {}} for state in manifest_states},
    }


def test_release_of_published_states_passes(tmp_path: Path) -> None:
    manifest = _write_release(
        tmp_path,
        manifest_states=PUBLISHED,
        plan_states=PUBLISHED,
        member_states=PUBLISHED,
    )

    check_release_states(manifest, tmp_path, PUBLISHED)


@pytest.mark.parametrize(
    ("field", "artifact"),
    [
        ("manifest_states", "manifest.json"),
        ("plan_states", "plan_index.json"),
        ("member_states", "members.json"),
    ],
)
def test_unpublished_state_in_any_artifact_is_refused(
    tmp_path: Path, field: str, artifact: str
) -> None:
    states: dict[str, list[str]] = {
        "manifest_states": PUBLISHED,
        "plan_states": PUBLISHED,
        "member_states": PUBLISHED,
    }
    states[field] = [*PUBLISHED, "TX"]
    manifest = _write_release(tmp_path, **states)

    with pytest.raises(PublishError, match=re.escape(f"{artifact} holds TX")):
        check_release_states(manifest, tmp_path, PUBLISHED)


def test_publish_refuses_before_contacting_r2(tmp_path: Path) -> None:
    manifest = _write_release(
        tmp_path,
        manifest_states=[*PUBLISHED, "TX"],
        plan_states=PUBLISHED,
        member_states=PUBLISHED,
    )
    manifest_file: Path = tmp_path / "manifest.json"
    manifest_file.write_text(json.dumps(manifest), "utf-8")
    # The gate refuses before any client exists, so these are never sent.
    settings = R2Settings(
        access_key_id="unused",
        secret_access_key="unused",  # noqa: S106
        account_id="unused",
        bucket="unused",
    )

    with pytest.raises(PublishError, match=re.escape("manifest.json holds TX")):
        publish_artifacts(
            manifest_file=manifest_file,
            derived_dir=tmp_path,
            basemap_file=tmp_path / "basemap.pmtiles",
            settings=settings,
            publish_states=PUBLISHED,
        )
