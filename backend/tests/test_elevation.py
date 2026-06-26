"""Tests for the M2 passive elevation branch: detector, scale, schema, crop
planner post-processing, bbox clamping, and branch resilience."""

from __future__ import annotations

import fitz  # PyMuPDF
import pytest

from app.services.extraction.pdf.config import PDFExtractionConfig
from app.services.extraction.pdf.elevation_crop_planner import PDFElevationCropPlanner
from app.services.extraction.pdf.elevation_crop_renderer import (
    PDFElevationCropRenderer,
    validate_clamp_bbox,
)
from app.services.extraction.pdf.elevation_detector import (
    PDFElevationDetector,
    extract_directions,
    extract_scale,
)
from app.services.extraction.pdf.fast_page_router import FastPageRoutingResult, RoutedPage
from app.services.extraction.pdf.models import RenderedPage
from app.services.extraction.pdf.renderer import PDFRenderer
from app.services.extraction.pdf.schemas import (
    ElevationCropPlanResponse,
    ElevationPageCandidate,
    ElevationRegion,
)
from app.services.extraction.pdf.service import PDFExtractionService


# ── Direction parsing ───────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "title, expected",
    [
        ("A-201.00 - WEST/EAST_ELEVATION", ["west", "east"]),
        ("A-202.00 - NORTH/SOUTH_ELEVATION", ["north", "south"]),
        ("A-201.00 - EAST & WEST ELEVATION", ["east", "west"]),
        ("FRONT ELEVATION", ["front"]),
        ("A-100.00 - FLOOR PLAN", []),
    ],
)
def test_extract_directions(title, expected):
    assert extract_directions(title) == expected


# ── Scale parsing ────────────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "text, expected",
    [
        ('SCALE: 3/32" = 1\'-0"', '3/32" = 1\'-0"'),
        ('1/8" = 1\'-0"', '1/8" = 1\'-0"'),
        ('3/16" = 1\'-0"', '3/16" = 1\'-0"'),
        ("SCALE: AS NOTED", "AS NOTED"),
        ("no scale here", None),
    ],
)
def test_extract_scale(text, expected):
    assert extract_scale(text) == expected


def test_specific_scale_beats_as_noted():
    assert extract_scale('AS NOTED elsewhere ... 1/8" = 1\'-0"') == '1/8" = 1\'-0"'


# ── Detector ─────────────────────────────────────────────────────────────────────

def _doc_with(lines):
    doc = fitz.open()
    page = doc.new_page()
    y = 72
    for ln in lines:
        page.insert_text((72, y), ln)
        y += 18
    return doc


def test_detector_returns_empty_without_candidates():
    doc = _doc_with(["nothing"])
    try:
        assert PDFElevationDetector().detect(doc, []) == []
    finally:
        doc.close()


def test_detector_builds_candidate_with_directions_and_scale():
    doc = _doc_with(["A-202.00", "NORTH / SOUTH ELEVATION", 'SCALE: 1/8" = 1\'-0"'])
    rp = RoutedPage(
        page_index=0, page_number=1, role="elevation",
        sheet_number="A-202.00", sheet_title="A-202.00 - NORTH/SOUTH_ELEVATION",
        confidence=0.95, source="pdf_outline", matched_terms=["ELEVATION"],
    )
    try:
        cands = PDFElevationDetector().detect(doc, [rp])
    finally:
        doc.close()
    assert len(cands) == 1
    c = cands[0]
    assert c.page_number == 1
    assert c.sheet_number == "A-202.00"
    assert c.directions == ["north", "south"]
    assert c.scale == '1/8" = 1\'-0"'
    assert c.source == "pdf_outline"


# ── Schema parsing ───────────────────────────────────────────────────────────────

def test_elevation_crop_plan_response_parses():
    payload = {
        "page_number": 10,
        "contains_elevation": True,
        "elevation_regions": [
            {"direction": "west", "bbox": [0.05, 0.1, 0.48, 0.8], "confidence": 0.9,
             "scale": '3/32" = 1\'-0"'},
            {"direction": "east", "bbox": [0.52, 0.1, 0.95, 0.8], "confidence": 0.88},
        ],
        "warnings": [],
    }
    resp = ElevationCropPlanResponse.model_validate(payload)
    assert resp.contains_elevation is True
    assert len(resp.elevation_regions) == 2
    # page identity defaults to 0 (filled deterministically by the planner later)
    assert resp.elevation_regions[0].page_number == 0
    assert resp.elevation_regions[0].direction == "west"


# ── bbox clamp helper ────────────────────────────────────────────────────────────

def test_validate_clamp_bbox():
    ok, clamped, _ = validate_clamp_bbox([0.1, 0.1, 0.9, 0.9])
    assert ok and clamped == [0.1, 0.1, 0.9, 0.9]

    # out-of-range values clamp into [0,1]
    ok, clamped, _ = validate_clamp_bbox([-0.2, 0.1, 1.4, 0.9])
    assert ok and clamped == [0.0, 0.1, 1.0, 0.9]

    # swapped corners get reordered
    ok, clamped, _ = validate_clamp_bbox([0.9, 0.9, 0.1, 0.1])
    assert ok and clamped == [0.1, 0.1, 0.9, 0.9]

    # full page is too large; degenerate is too small
    assert validate_clamp_bbox([0, 0, 1, 1])[0] is False
    assert validate_clamp_bbox([0, 0, 0.02, 0.02])[0] is False
    assert validate_clamp_bbox([1, 2, 3])[0] is False  # wrong length


# ── Crop planner post-processing (no network) ────────────────────────────────────

class _FakeLLM:
    model_name = "fake"

    def __init__(self, response):
        self._response = response

    def with_structured_output(self, schema):
        return schema

    def invoke_multimodal(self, structured_llm, prompt, image_data_uris):
        return self._response


def test_crop_planner_stamps_pages_truncates_and_normalizes():
    canned = ElevationCropPlanResponse(
        page_number=0,
        contains_elevation=True,
        elevation_regions=[
            ElevationRegion(direction="WEST", bbox=[0.1, 0.1, 0.5, 0.9], confidence=0.9),
            ElevationRegion(direction="east", bbox=[0.5, 0.1, 0.9, 0.9], confidence=0.9),
            ElevationRegion(direction="banana", bbox=[0.1, 0.1, 0.3, 0.3]),
            ElevationRegion(direction="north", bbox=[0.1, 0.1, 0.3, 0.3]),
            ElevationRegion(direction="south", bbox=[0.1, 0.1, 0.3, 0.3]),  # 5th -> dropped
        ],
        warnings=[],
    )
    config = PDFExtractionConfig.from_settings()
    planner = PDFElevationCropPlanner(config, _FakeLLM(canned))
    candidate = ElevationPageCandidate(
        page_index=9, page_number=10, sheet_number="A-201.00",
        directions=["west", "east"], scale='3/32" = 1\'-0"',
    )
    rp = RenderedPage(
        page_index=9, page_number=10, png_path="x.png",
        data_uri="data:image/png;base64,AAAA", width_px=10, height_px=10, dpi=150,
    )

    resp = planner.plan(candidate, rp, native_text="some text")

    assert len(resp.elevation_regions) == 4  # truncated to MAX 4
    assert resp.page_number == 10
    first = resp.elevation_regions[0]
    assert first.direction == "west"          # lowercased
    assert first.page_number == 10 and first.page_index == 9  # stamped
    assert first.sheet_number == "A-201.00"   # backfilled
    assert first.scale == '3/32" = 1\'-0"'    # backfilled from candidate
    # invalid direction normalized to "unknown"
    assert resp.elevation_regions[2].direction == "unknown"


# ── Branch resilience ────────────────────────────────────────────────────────────

def test_elevation_branch_never_raises_on_llm_error(tmp_path):
    config = PDFExtractionConfig.from_settings()
    doc = _doc_with(["A-201.00", "EAST & WEST ELEVATION", 'SCALE: 3/32" = 1\'-0"'])
    rp = RoutedPage(
        page_index=0, page_number=1, role="elevation",
        sheet_number="A-201.00", sheet_title="A-201.00 - EAST & WEST ELEVATION",
        confidence=0.95, source="pdf_outline", matched_terms=["ELEVATION"],
    )
    routing = FastPageRoutingResult(
        schedule_candidates=[], elevation_candidates=[rp],
        project_info_candidates=[], confidence="high", used_fast_path=False,
    )

    class _BrokenLLM:
        model_name = "broken"

        def with_structured_output(self, schema):
            raise RuntimeError("boom")

        def invoke_multimodal(self, *a, **k):
            raise RuntimeError("boom")

    svc = PDFExtractionService(config)
    renderer = PDFRenderer(config)
    try:
        payload = svc._run_elevation_branch(doc, routing, {}, renderer, _BrokenLLM(), tmp_path)
    finally:
        doc.close()

    assert payload["enabled"] is True
    assert payload["warnings"], "branch should record the error as a warning, not raise"


def test_elevation_branch_noop_without_candidates(tmp_path):
    config = PDFExtractionConfig.from_settings()
    doc = _doc_with(["nothing"])
    routing = FastPageRoutingResult(
        schedule_candidates=[], elevation_candidates=[],
        project_info_candidates=[], confidence="low", used_fast_path=False,
    )
    svc = PDFExtractionService(config)
    renderer = PDFRenderer(config)
    try:
        payload = svc._run_elevation_branch(doc, routing, {}, renderer, None, tmp_path)
    finally:
        doc.close()
    assert payload["enabled"] is False
    assert payload["pages"] == [] and payload["regions"] == []
