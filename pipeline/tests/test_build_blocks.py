from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from blocks_world import (
    BLOCK_COUNT,
    CONGRESS_END,
    CONGRESS_START,
    NATIONAL_113_SPLIT,
    POLYGON_SPLIT,
    STATE_115_SPLIT,
    BlockWorld,
    block_geoid,
    make_block_world,
)

from pipeline.blocks import BlocksBuildError
from pipeline.plans import Plan


@pytest.fixture
def world(tmp_path: Path) -> BlockWorld:
    return make_block_world(tmp_path)


def _sources_by_congress(world: BlockWorld) -> dict[int, dict[str, Any]]:
    return {
        entry["congress"]: entry["block_source"]
        for entry in world.output()["congresses"]
    }


def _expected_history(index: int) -> list[int | None]:
    return [
        POLYGON_SPLIT[index],
        NATIONAL_113_SPLIT[index],
        NATIONAL_113_SPLIT[index],
        STATE_115_SPLIT[index],
    ]


def test_output_envelope_describes_itself(world: BlockWorld) -> None:
    world.build()
    output: dict[str, Any] = world.output()

    assert output["schema_version"] == 1
    assert output["state"] == "NC"
    assert output["chamber"] == "congressional"
    assert output["congress_start"] == CONGRESS_START
    assert output["congress_end"] == CONGRESS_END
    assert [entry["congress"] for entry in output["congresses"]] == [112, 113, 114, 115]


def test_blocks_are_keyed_by_2020_geoid(world: BlockWorld) -> None:
    result = world.build()

    expected: set[str] = {block_geoid("v2020", i) for i in range(BLOCK_COUNT)}
    assert set(world.output()["blocks"]) == expected
    assert result.blocks_count == BLOCK_COUNT


def test_each_congress_uses_the_highest_precedence_source(world: BlockWorld) -> None:
    world.build()
    sources: dict[int, dict[str, Any]] = _sources_by_congress(world)

    assert sources[112]["type"] == "polygon_join"
    assert sources[112]["block_vintage"] == "v2000"
    assert sources[113]["upstream_url"].endswith("/national_cd113.zip")
    assert sources[114]["upstream_url"].endswith("/national_cd113.zip")
    assert sources[115]["upstream_url"].endswith("/NC_cd115.zip")


def test_block_source_types_are_the_frontend_contract(world: BlockWorld) -> None:
    world.build()
    sources: dict[int, dict[str, Any]] = _sources_by_congress(world)

    assert set(sources[112]) == {
        "type",
        "block_vintage",
        "provider",
        "source_file",
        "upstream_landing_url",
    }
    assert set(sources[113]) == {
        "type",
        "block_vintage",
        "provider",
        "inner_filename",
        "upstream_url",
        "upstream_landing_url",
    }
    assert sources[113]["type"] == "delimited_assignment"


@pytest.mark.parametrize("index", range(BLOCK_COUNT))
def test_history_follows_each_congress_source(world: BlockWorld, index: int) -> None:
    world.build()

    assert world.history_of(index) == _expected_history(index)


def test_identical_histories_are_stored_once(world: BlockWorld) -> None:
    world.assignments = []
    world.carries = []

    result = world.build(allow_missing=True)

    assert result.histories_count == len(set(POLYGON_SPLIT))
    assert len(world.output()["histories"]) == result.histories_count


def test_carries_are_reported_in_warnings(world: BlockWorld) -> None:
    result = world.build()

    carry_warnings: list[str] = [w for w in result.warnings if "Carried" in w]
    assert len(carry_warnings) == 1
    assert "114<-113" in carry_warnings[0]
    assert "115<-" not in carry_warnings[0]


def test_two_builds_write_identical_bytes(world: BlockWorld) -> None:
    world.build()
    first: bytes = world.output_path.read_bytes()
    world.build()

    assert world.output_path.read_bytes() == first


def test_unconfigured_bef_era_congress_raises(world: BlockWorld) -> None:
    world.assignments = [a for a in world.assignments if a.congress != 113]
    world.carries = [c for c in world.carries if c.congress != 114]

    with pytest.raises(BlocksBuildError, match="Congress 113"):
        world.build()

    assert not world.output_path.exists()


def test_allow_missing_writes_null_for_unsourced_congresses(world: BlockWorld) -> None:
    world.assignments = [a for a in world.assignments if a.congress != 113]
    world.carries = [c for c in world.carries if c.congress != 114]

    result = world.build(allow_missing=True)

    assert result.unsourced_congresses == [113, 114]
    sources: dict[int, dict[str, Any]] = _sources_by_congress(world)
    assert sources[113] == {"type": "unsourced"}
    assert world.history_of(0)[1:3] == [None, None]


def test_carry_needs_a_target_in_its_own_scope(world: BlockWorld) -> None:
    # 113 resolves from a state file, so the national 114<-113 carry finds no
    # national file to borrow.
    world.assignments = [
        world.write_bef(state="NC", congress=113, split=NATIONAL_113_SPLIT),
        *[a for a in world.assignments if a.congress != 113],
    ]

    with pytest.raises(BlocksBuildError, match="same_as_congress=113"):
        world.build()


def test_uncovered_congress_raises(world: BlockWorld) -> None:
    world.plans = [world.plans[0], _single_plan(world, 113, 114)]

    with pytest.raises(BlocksBuildError, match=r"no in-scope plan covers .*\[115\]"):
        world.build()


def test_overlapping_plans_raise(world: BlockWorld) -> None:
    world.plans = [world.plans[0], _single_plan(world, 112, 115)]

    with pytest.raises(BlocksBuildError, match="two plans claim Congress 112"):
        world.build()


def test_open_ended_plan_covers_the_rest_of_scope(world: BlockWorld) -> None:
    world.plans = [world.plans[0], _single_plan(world, 113, None)]

    world.build()

    assert world.history_of(3) == _expected_history(3)


def test_missing_tabblock_zip_raises(world: BlockWorld) -> None:
    for zip_path in (world.paths.tabblock_dir / "2000").rglob("*.zip"):
        zip_path.unlink()

    with pytest.raises(BlocksBuildError, match="tabblock zip for vintage v2000"):
        world.build()


def _single_plan(world: BlockWorld, start: int, end: int | None) -> Plan:
    """Return a plan over [start, end] that reuses the first plan's polygons."""
    return world.plans[0].model_copy(
        update={
            "plan_id": f"NC_{start}_{2011 + 2 * (start - 112)}",
            "congress_start": start,
            "congress_end": end,
        }
    )
