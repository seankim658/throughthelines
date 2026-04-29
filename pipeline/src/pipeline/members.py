"""Slice voteview HSall_members.csv into per-state/congress/district lookup.

Reads the csv, filters rows, translates ICPSR party codes to single letter
strings, and writes a nested JSON lookup in the format:

    members[state][congress][district] -> list of member records
"""

from __future__ import annotations
import os
import json
import csv
from dataclasses import dataclass
from pathlib import Path
from typing import cast, Any

from pipeline.config import ScopeSettings
from pipeline.state_codes import StateCode

_REQUIRED_COLUMNS: frozenset[str] = frozenset(
    {
        "congress",
        "chamber",
        "state_abbrev",
        "district_code",
        "party_code",
        "icpsr",
        "bioname",
        "bioguide_id",
        "born",
        "died",
        "nominate_dim1",
        "nominate_dim2",
        "nokken_poole_dim1",
        "nokken_poole_dim2",
    }
)

_PARTY_CODES: dict[str, str] = {"100": "D", "200": "R", "328": "I"}

_UNKNOWN_PARTY: str = "?"

MemberRecord = dict[str, object]
MembersByDistrict = dict[str, list[MemberRecord]]
MembersByCongress = dict[str, MembersByDistrict]
MembersByState = dict[str, MembersByCongress]

# --- Errors ---


class MembersBuildError(Exception):
    """Raised when the members slice cannot complete."""


# --- Models ---


@dataclass(frozen=True)
class _SliceRow:

    state: StateCode
    congress: int
    district: int
    icpsr: int
    name: str
    party: str
    bioguide_id: str
    born: int | None
    died: int | None
    nominate_dim1: float | None
    nominate_dim2: float | None
    nokken_poole_dim1: float | None
    nokken_poole_dim2: float | None


@dataclass(frozen=True)
class MembersBuildResult:

    output_path: Path
    rows_read: int
    rows_in_scope: int
    districts_covered: int
    warnings: list[str]


# --- API ---


def build_members(
    scope: ScopeSettings, voteview_csv_path: Path, output_path: Path
) -> MembersBuildResult:
    if not voteview_csv_path.exists():
        raise MembersBuildError(
            f"voteview CSV not found at {voteview_csv_path} "
            f"(did you run `pipeline fetch`?)"
        )

    warnings: list[str] = []
    sliced_rows: list[_SliceRow] = []
    rows_read: int = 0

    try:
        with voteview_csv_path.open(encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            if reader.fieldnames is None:
                raise MembersBuildError(
                    f"voteview CSV at {voteview_csv_path} has no header rows"
                )
            _validate_columns(list(reader.fieldnames), voteview_csv_path)

            for row_idx, raw in enumerate(reader, start=2):
                rows_read += 1
                sliced: _SliceRow | None = _parse_row(raw, row_idx, scope, warnings)
                if sliced is not None:
                    sliced_rows.append(sliced)

    except OSError as e:
        raise MembersBuildError(f"could not read {voteview_csv_path}: {e}") from e

    grouped: MembersByState = _group_and_sort(sliced_rows)
    districts_covered: int = sum(
        len(by_district)
        for by_congress in grouped.values()
        for by_district in by_congress.values()
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    _write_json_atomic(output_path, grouped)

    return MembersBuildResult(
        output_path=output_path,
        rows_read=rows_read,
        rows_in_scope=len(sliced_rows),
        districts_covered=districts_covered,
        warnings=warnings,
    )


# --- Helpers ---


def _validate_columns(header: list[str], csv_path: Path) -> None:
    present: set[str] = set(header)
    missing: list[str] = sorted(_REQUIRED_COLUMNS - present)
    if missing:
        raise MembersBuildError(f"missing required column(s) in {csv_path}: {missing}")


def _parse_row(
    raw: dict[str, str], row_idx: int, scope: ScopeSettings, warnings: list[str]
) -> _SliceRow | None:
    state_abbrev: str = (raw.get("state_abbrev") or "").strip()
    if state_abbrev not in scope.chambers:
        return None
    state: StateCode = cast(StateCode, state_abbrev)

    chamber_raw: str = (raw.get("chamber") or "").strip()
    if chamber_raw != "House":
        return None
    if "congressional" not in scope.chambers[state]:
        return None

    congress: int = _parse_int(raw, "congress", row_idx)
    if not (scope.congress_start <= congress <= scope.congress_end):
        return None

    district_code: int = _parse_int(raw, "district_code", row_idx)
    if district_code < 0:
        return None
    if district_code == 0:
        icpsr_str: str = (raw.get("icpsr") or "").strip()
        warnings.append(
            f"row {row_idx}: district_code == 0 in scope "
            f"(congress={congress}, state={state}, icpsr={icpsr_str!r})"
        )
        return None

    icpsr: int = _parse_int(raw, "icpsr", row_idx)

    party_code: str = (raw.get("party_code") or "").strip()
    party: str = _PARTY_CODES.get(party_code, _UNKNOWN_PARTY)
    if party == _UNKNOWN_PARTY:
        warnings.append(
            f"row {row_idx}: unrecognized party_code "
            f"(icpsr={icpsr}, congress={congress}, party_code={party_code!r})"
        )

    name: str = (raw.get("bioname") or "").strip()
    if not name:
        raise MembersBuildError(
            f"row {row_idx}: empty 'bioname' in in-scope row "
            f"(icpsr={icpsr}, congress={congress})"
        )
    bioguide_id: str = (raw.get("bioguide_id") or "").strip()

    return _SliceRow(
        state=state,
        congress=congress,
        district=district_code,
        icpsr=icpsr,
        name=name,
        party=party,
        bioguide_id=bioguide_id,
        born=_parse_optional_int(raw, "born", row_idx),
        died=_parse_optional_int(raw, "died", row_idx),
        nominate_dim1=_parse_optional_float(raw, "nominate_dim1", row_idx),
        nominate_dim2=_parse_optional_float(raw, "nominate_dim2", row_idx),
        nokken_poole_dim1=_parse_optional_float(raw, "nokken_poole_dim1", row_idx),
        nokken_poole_dim2=_parse_optional_float(raw, "nokken_poole_dim2", row_idx),
    )


def _parse_int(raw: dict[str, str], column: str, row_idx: int) -> int:
    value: str = (raw.get(column) or "").strip()
    if not value:
        raise MembersBuildError(
            f"row {row_idx}: missing required value in column {column!r}"
        )
    try:
        as_float: float = float(value)
    except ValueError as e:
        raise MembersBuildError(
            f"row {row_idx}: malformed {column!r} value {value!r} "
            f"(expected integer)"
        ) from e
    as_int: int = int(as_float)
    if as_int != as_float:
        raise MembersBuildError(
            f"row {row_idx}: {column!r} value {value!r} is not a whole number"
        )
    return as_int


def _parse_optional_int(raw: dict[str, str], column: str, row_idx: int) -> int | None:
    value: str = (raw.get(column) or "").strip()
    if not value:
        return None
    try:
        as_float: float = float(value)
    except ValueError as e:
        raise MembersBuildError(
            f"row {row_idx}: malformed {column!r} value {value!r} "
            f"(expected integer or empty)"
        ) from e
    as_int: int = int(as_float)
    if as_int != as_float:
        raise MembersBuildError(
            f"row {row_idx}: {column!r} value {value!r} is not a whole number"
        )
    return as_int


def _parse_optional_float(
    raw: dict[str, str], column: str, row_index: int
) -> float | None:
    value: str = (raw.get(column) or "").strip()
    if not value:
        return None
    try:
        return float(value)
    except ValueError as e:
        raise MembersBuildError(
            f"row {row_index}: malformed {column!r} value {value!r} "
            f"(expected float or empty)"
        ) from e


def _group_and_sort(rows: list[_SliceRow]) -> MembersByState:
    """Build the nested {state: {district: [member, ...]}} shape."""
    out: MembersByState = {}
    for row in rows:
        congress_key: str = str(row.congress)
        district_key: str = str(row.district)
        by_congress: MembersByCongress = out.setdefault(row.state, {})
        by_district: MembersByDistrict = by_congress.setdefault(congress_key, {})
        leaf: list[MemberRecord] = by_district.setdefault(district_key, [])
        leaf.append(_row_to_member_dict(row))

    for by_congress in out.values():
        for by_district in by_congress.values():
            for leaf in by_district.values():
                leaf.sort(key=lambda member: cast(int, member["icpsr"]))

    return out


def _row_to_member_dict(row: _SliceRow) -> MemberRecord:
    return {
        "name": row.name,
        "party": row.party,
        "icpsr": row.icpsr,
        "bioguide_id": row.bioguide_id,
        "born": row.born,
        "died": row.died,
        "nominate_dim1": row.nominate_dim1,
        "nominate_dim2": row.nominate_dim2,
        "nokken_poole_dim1": row.nokken_poole_dim1,
        "nokken_poole_dim2": row.nokken_poole_dim2,
    }


def _write_json_atomic(dest_path: Path, payload: Any) -> None:
    tmp_path: Path = dest_path.with_suffix(dest_path.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, separators=(",", ":"))
    os.replace(tmp_path, dest_path)
