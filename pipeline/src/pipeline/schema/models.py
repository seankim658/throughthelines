"""Pydantic models for a single plan-metadata record.

Each plan in a state's redistricting history is stored as one YAML file
validated against the `Plan` model. Validation of a single file is
independent (cross-plan checks in `validators.py`).

Missingness model:
    Curation-sensitive fields accept three kinds of values:
        - A real value (e.g., `origin: "legislature"`)
        - The string "unknown" (curated and not determinable)
        - The string "pending" (not yet curated)
    Factual fields (plan_id, state, congress_start, etc.) do not support
    missingness and must be real values. CI fails on any factual field
    that is missing or malformed.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Annotated, Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    field_validator,
    model_validator,
)

# Sentinel strings
PENDING: Literal["pending"] = "pending"
UNKNOWN: Literal["unknown"] = "unknown"

# A field whose real value is a string may be that string, "unknown" or
# "pending". A field whose real value is a bool follows the same pattern.
# We spell these out explicitly for each field family rather than using a
# generic so that Pydantic's error messages stay readable.

OriginLiteral = Literal[
    "legislature",
    "court",
    "commission",
    "remedial",
    "unchanged",
]
OriginField = OriginLiteral | Literal["unknown", "pending"]
DateField = date | Literal["unknown", "pending"] | None

StruckDownField = bool | Literal["unknown", "pending"]

CurationStatusField = Literal["pending", "partial", "curated"]
StateCode = Literal["NC"]

# A free-prose field that may be a real string, "unknown", or "pending".
# The distinction between a real value and sentinels is by exact string
# match, so callers reading these fields must check for the sentinels
# explicitly before treating the value as prose.
ProseField = str

# A plan ID reference (used in predecessor / superseded_by). Either a
# real plan_id string, the sentinel "pending", or None.
PlanRefField = str | None

# --- Sub-Models ---


class CourtCitation(BaseModel):
    """A court opinion cited in a plan's history."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    case: str = Field(
        ..., min_length=1, description="Short case name, e.g., 'Harper v. Hall'."
    )
    citation: str = Field(..., min_length=1, description="Formal citation string.")
    role: Literal["enabling", "invalidating", "remedial", "affirming", "context"] = (
        Field(..., description="How this case relates to the plan.")
    )
    url: HttpUrl = Field(..., description="Live URL to the opinion.")
    archived_url: HttpUrl | None = Field(
        default=None, description="Wayback or archive.org snapshot URL."
    )


class Source(BaseModel):
    """An external source consulted when curating this plan's metadata."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    url: HttpUrl
    accessed: date = Field(
        ..., description="Date the source was consulted (YYYY-MM-DD)."
    )
    archived: HttpUrl | None = Field(
        default=None, description="Wayback or archive.org snapshot URL, if captured."
    )


# --- Plan Models ---

PLAN_ID_PATTERN: re.Pattern[str] = re.compile(r"^[A-Z]{2}_\d{3}_\d{4}$")


class Plan(BaseModel):
    """One plan record in the plan-metadata dataset.

    Field groups:
        Identity & provenance (factual, must be real values):
            plan_id, state, chamber, congress_start, congress_end,
            source_file, source_commit, schema_version

        Dates (may be null for plans that predate/post-date a known date):
            enacted_date, effective_date

        Curation-sensitive (three-valued: real / "unknown" / "pending"):
            origin, origin_details, struck_down, struck_down_details,
            struck_down_districts, superseded_by, predecessor,
            court_citations, sources, notes

        Completeness tracking:
            curation_status, curation_last_reviewed

        Open extensions:
            extensions (free-form dict, passed through untouched)
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    # Identity & provenance
    plan_id: Annotated[str, Field(pattern=PLAN_ID_PATTERN.pattern, min_length=1)]
    state: StateCode
    chamber: Literal["congressional"]
    congress_start: Annotated[int, Field(ge=103, le=130)]
    congress_end: Annotated[int, Field(ge=103, le=130)] | None
    source_file: Annotated[str, Field(min_length=1)]
    source_commit: Annotated[str, Field(min_length=1)]
    schema_version: Literal[1]

    # Dates
    enacted_date: DateField = PENDING
    effective_date: DateField = PENDING

    # Curation-sensitive fields
    origin: OriginField = PENDING
    origin_details: ProseField = PENDING

    struck_down: StruckDownField = PENDING
    struck_down_details: ProseField = PENDING
    struck_down_districts: list[int] = Field(default_factory=list)

    superseded_by: PlanRefField = PENDING
    predecessor: PlanRefField = PENDING

    court_citations: list[CourtCitation] = Field(default_factory=list)
    sources: list[Source] = Field(default_factory=list)
    notes: ProseField = PENDING

    # Status tracking
    curation_status: CurationStatusField = PENDING
    curation_last_reviewed: date | None = None

    # Open extensions
    # Free-form namespace. Keys and values are whatever future contributors
    # need; the pipeline preserves them unchanged.
    extensions: dict[str, Any] = Field(default_factory=dict)

    # Validators

    @field_validator("plan_id")
    @classmethod
    def _plan_id_matches_pattern(cls, value: str) -> str:
        """Ensures plan_id follows the STATE_CONGRESS_YEAR pattern."""
        if not PLAN_ID_PATTERN.match(value):
            raise ValueError(
                f"plan_id must match pattern STATE_CONGRESS_YEAR (e.g., NC_118_2023); got {value!r}"
            )
        return value

    @field_validator("predecessor", "superseded_by")
    @classmethod
    def _plan_reference_is_well_formed(cls, value: str | None) -> str | None:
        """A plan reference must be None, the sentinel 'pending', or a well-formed plan_id matching PLAN_ID_PATTERN."""
        if value is None or value == PENDING:
            return value
        if not PLAN_ID_PATTERN.match(value):
            raise ValueError(
                f"plan reference must be null, 'pending', or a plan_id "
                f"matching STATE_CONGRESS_YEAR (e.g., NC_118_2023); got {value!r}"
            )
        return value

    @model_validator(mode="after")
    def _congress_range_is_ordered(self) -> Plan:
        """Ensure congress_end is not before congress_start."""
        if self.congress_end is not None and self.congress_end < self.congress_start:
            raise ValueError(
                f"congress_end({self.congress_end}) must be >= congress_start ({self.congress_start})"
            )
        return self

    @model_validator(mode="after")
    def _plan_id_matches_state_and_congress(self) -> Plan:
        """Ensure plan_id prefix matches the declared state and congress_start."""
        parts: list[str] = self.plan_id.split("_")
        if len(parts) != 3:
            raise ValueError(
                f"plan_id {self.plan_id!r} does not have the expected "
                f"STATE_CONGRESS_YEAR structure"
            )
        state_from_id, congress_from_id, _ = parts
        if state_from_id != self.state:
            raise ValueError(
                f"plan_id state prefix ({state_from_id}) does not match state field ({self.state})"
            )
        if not congress_from_id.isdigit():
            raise ValueError(
                f"plan_id congress segment {congress_from_id!r} is not numeric"
            )
        if int(congress_from_id) != self.congress_start:
            raise ValueError(
                f"plan_id congress ({congress_from_id}) does not match congress_start ({self.congress_start})"
            )
        return self
