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
    write_district_polygons,
)
from shapely.geometry import box

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


def test_spatial_join_fallback_uses_the_congress_own_decade(
    world: BlockWorld,
) -> None:
    world.plans = [world.plans[0], world.add_plan("NC_113_2013", 113, 115)]
    world.assignments = [a for a in world.assignments if a.congress != 113]
    world.carries = [c for c in world.carries if c.congress != 114]

    world.build(spatial_join_fallback=True)
    sources: dict[int, dict[str, Any]] = _sources_by_congress(world)

    assert sources[113]["type"] == "polygon_join"
    assert sources[113]["block_vintage"] == "v2010"
    assert sources[114]["block_vintage"] == "v2010"
    assert [world.history_of(i)[1] for i in range(BLOCK_COUNT)] == list(POLYGON_SPLIT)


def test_spatial_join_fallback_in_the_2020_cycle_uses_2020_blocks(
    world: BlockWorld,
) -> None:
    world.congress_start = 118
    world.congress_end = 118
    world.plans = [world.add_plan("NC_118_2023", 118, 118)]
    world.assignments = []
    world.carries = []

    world.build(spatial_join_fallback=True)

    assert _sources_by_congress(world)[118]["block_vintage"] == "v2020"
    assert [world.history_of(i)[0] for i in range(BLOCK_COUNT)] == list(POLYGON_SPLIT)


def test_spatial_join_fallback_past_2020_cycle_raises(world: BlockWorld) -> None:
    world.congress_start = 123
    world.congress_end = 123
    world.plans = [world.add_plan("NC_123_2033", 123, 123)]
    world.assignments = []
    world.carries = []

    with pytest.raises(BlocksBuildError, match="Congress 123"):
        world.build(spatial_join_fallback=True)


def test_plan_spanning_two_decades_joins_each_decade_separately(
    world: BlockWorld,
) -> None:
    # One plan covers the 112th (2000 blocks) and the 113th (2010 blocks).
    spanning: Plan = world.add_plan("NC_112_2011", 112, 113)
    world.plans = [spanning, world.add_plan("NC_114_2015", 114, 115)]
    world.assignments = [a for a in world.assignments if a.congress != 113]
    world.carries = [c for c in world.carries if c.congress != 114]

    world.build(spatial_join_fallback=True)

    for index in range(BLOCK_COUNT):
        assert world.history_of(index)[:2] == [POLYGON_SPLIT[index]] * 2


def test_polygon_fallback_warning_names_each_vintage(world: BlockWorld) -> None:
    world.plans = [world.plans[0], world.add_plan("NC_113_2013", 113, 115)]
    world.assignments = [a for a in world.assignments if a.congress != 113]
    world.carries = [c for c in world.carries if c.congress != 114]

    result = world.build(spatial_join_fallback=True)
    fallback: list[str] = [w for w in result.warnings if "Polygon-fallback" in w]

    assert len(fallback) == 2
    assert "[112]" in fallback[0]
    assert "block_vintage=v2000" in fallback[0]
    assert "[113, 114]" in fallback[1]
    assert "block_vintage=v2010" in fallback[1]


def test_block_outside_every_district_is_null_and_reported(
    world: BlockWorld,
) -> None:
    plan_112: Plan = world.plans[0]
    # District 2 stops short of block 3, so block 3 lies in no district.
    write_district_polygons(
        world.paths.raw_dir / plan_112.source_file,
        {1: box(0, 0, 2, 1), 2: box(2, 0, 3, 1)},
    )

    result = world.build()
    unmatched: list[str] = [w for w in result.warnings if "outside every" in w]

    assert world.history_of(3)[0] is None
    assert len(unmatched) == 1
    assert "1 of 4 v2000 block(s)" in unmatched[0]
    assert plan_112.source_file in unmatched[0]
    assert "[112]" in unmatched[0]


def test_no_unmatched_warning_when_every_block_lands(world: BlockWorld) -> None:
    result = world.build()

    assert not [w for w in result.warnings if "outside every" in w]


def _single_plan(world: BlockWorld, start: int, end: int | None) -> Plan:
    """Return a plan over [start, end] that reuses the first plan's polygons."""
    return world.plans[0].model_copy(
        update={
            "plan_id": f"NC_{start}_{2011 + 2 * (start - 112)}",
            "congress_start": start,
            "congress_end": end,
        }
    )
