"""LangChain structured-output Pydantic models.

Ported verbatim from NOTEBOOKS/pdf_algo_test.py — schema fields unchanged.
"""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class CropRegionPlan(BaseModel):
    label: str = Field(description="Human-readable label for the crop region, e.g. 'main window schedule table'.")
    normalized_bbox: List[float] = Field(
        description=(
            "Crop box as [x0, y0, x1, y1], normalized to the full page image/page bounds. "
            "0 means left/top, 1 means right/bottom."
        )
    )
    confidence: float = Field(description="Confidence that this crop contains the relevant schedule details.")
    reason: str = Field(description="Why this crop region is needed and what it should contain.")


class CropPlanResponse(BaseModel):
    page_number: int
    contains_schedule: bool
    schedule_type: str = Field(
        description=(
            "One of: window_schedule, opening_schedule, glazing_schedule, fenestration_schedule, "
            "mixed_door_window_schedule, door_only_schedule, elevation_with_window_info, not_relevant, unknown"
        )
    )
    readability: str = Field(
        description="One of: clear_enough, too_small, blurry, partial, not_readable, unknown."
    )
    can_extract_without_crop: bool
    needs_crop: bool
    crop_regions: List[CropRegionPlan]
    confidence: float
    reason: str
    warnings: List[str]


class ExtractedScheduleRow(BaseModel):
    """A single window/opening/glazing schedule row."""

    tag: str
    material_type: str
    width: str
    height: str
    area: str
    quantity: str
    opening_type: str
    material: str
    u_value: str
    shgc: str
    vt: str
    glass_type: str
    confidence: float
    notes: str


class ExtractedDoorRow(BaseModel):
    """A single door schedule row.

    No `area` field on purpose: door area is recomputed deterministically from
    width/height after extraction (the LLM must not compute area). NFRC fields
    (u_value/shgc/vt) are window-specific and intentionally omitted for doors.
    """

    tag: str
    opening_type: str
    quantity: str
    width: str
    height: str
    material: str
    fire_rating: str
    self_closing: str
    glass_type: str
    notes: str
    confidence: float


class ExtractionPageClassification(BaseModel):
    contains_schedule: bool
    schedule_type: str
    confidence: float
    reason: str


class ExtractionPageResponse(BaseModel):
    page_number: int
    page_classification: ExtractionPageClassification
    window_rows: List[ExtractedScheduleRow]
    door_rows: List[ExtractedDoorRow]
    warnings: List[str]


class ProjectInfoResponse(BaseModel):
    """Project-level metadata extracted from cover/title/general-info pages.

    All fields are strings. Empty string means the value was not visible.
    """

    project_name: str = Field(default="", description="Project or building name, exactly as shown.")
    site_address: str = Field(default="", description="Street address. Empty if not visible.")
    city: str = Field(default="", description="City name. Empty if not visible.")
    state: str = Field(default="", description="Two-letter US state code if visible (e.g. NY). Empty otherwise.")
    zip_code: str = Field(default="", description="Postal code. Empty if not visible.")


# ── Elevation (M2): passive directional elevation detection + crop planning ─────
#
# Direction is normalized lowercase to one of:
#   east, west, north, south, front, rear, left, right, unknown.

ELEVATION_DIRECTIONS = (
    "east", "west", "north", "south", "front", "rear", "left", "right", "unknown",
)


class ElevationPageCandidate(BaseModel):
    """Deterministic per-page elevation metadata (produced without LLM/render)."""

    page_index: int
    page_number: int
    sheet_number: Optional[str] = None
    sheet_title: Optional[str] = None
    directions: List[str] = Field(default_factory=list)
    scale: Optional[str] = None
    source: Optional[str] = None
    confidence: float = 0.0
    reason: Optional[str] = None


class ElevationRegion(BaseModel):
    """One directional elevation drawing region on a page.

    page_index/page_number default to 0 so the structured-output LLM does not
    have to fill them; the pipeline overwrites them with the real page after the
    crop-planning call.
    """

    page_index: int = 0
    page_number: int = 0
    sheet_number: Optional[str] = None
    direction: str = Field(description="One of: east, west, north, south, front, rear, left, right, unknown.")
    scale: Optional[str] = None
    bbox: List[float] = Field(
        description="Normalized [x0, y0, x1, y1] in 0..1; top-left origin."
    )
    confidence: float = 0.0
    reason: Optional[str] = None


class ElevationCropPlanResponse(BaseModel):
    page_number: int
    contains_elevation: bool
    elevation_regions: List[ElevationRegion]
    warnings: List[str] = Field(default_factory=list)
