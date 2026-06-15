"""Tests for the fast deterministic page router.

These build tiny in-memory PDFs with PyMuPDF (text + optional outline/TOC) and
assert the router's routing decisions. No rendering and no LLM are involved.
"""

from __future__ import annotations

from typing import List, Optional, Tuple

import fitz  # PyMuPDF
import pytest

from app.services.extraction.pdf.fast_page_router import FastPageRouter


def _make_pdf(
    pages: List[List[str]],
    toc: Optional[List[Tuple[int, str, int]]] = None,
) -> fitz.Document:
    """Build an in-memory PDF. `pages` is a list of pages, each a list of text
    lines. `toc` is an optional list of (level, title, page_number_1based)."""
    doc = fitz.open()
    for lines in pages:
        page = doc.new_page()
        y = 72
        for line in lines:
            page.insert_text((72, y), line)
            y += 18
    if toc:
        doc.set_toc([[level, title, page] for (level, title, page) in toc])
    return doc


def _route(pages, toc=None):
    doc = _make_pdf(pages, toc)
    try:
        return FastPageRouter().route(doc)
    finally:
        doc.close()


# ── Outline-driven high confidence ─────────────────────────────────────────────

def test_outline_combined_schedule_is_high_confidence():
    # A-401.00 - WINDOW, DOOR, WALL & FLOOR SCHEDULE on page 2 via outline.
    result = _route(
        pages=[
            ["COVER SHEET", "PROJECT XYZ"],
            ["A-401.00", "schedule table goes here", "W-1 36 48"],
            ["A-100.00", "FLOOR PLAN"],
        ],
        toc=[(1, "A-401.00 - WINDOW, DOOR, WALL & FLOOR SCHEDULE", 2)],
    )

    assert result.confidence == "high"
    assert result.used_fast_path is True
    assert len(result.schedule_candidates) == 1

    cand = result.schedule_candidates[0]
    assert cand.page_number == 2
    assert cand.role == "combined_schedule"
    assert cand.source == "pdf_outline"
    assert cand.confidence == pytest.approx(0.95)


def test_outline_elevation_is_high_confidence():
    # A-201.00 - WEST/EAST_ELEVATION via outline. No schedule present, so the
    # router stays "high" but does NOT take the fast path (schedule discovery
    # must not be skipped when no schedule page was found).
    result = _route(
        pages=[
            ["COVER SHEET"],
            ["A-201.00", "building elevation drawing"],
        ],
        toc=[(1, "A-201.00 - WEST/EAST_ELEVATION", 2)],
    )

    assert result.confidence == "high"
    assert result.used_fast_path is False  # no schedule candidate → fall back
    assert len(result.elevation_candidates) == 1

    elev = result.elevation_candidates[0]
    assert elev.page_number == 2
    assert elev.role == "elevation"
    assert elev.source == "pdf_outline"
    assert elev.confidence == pytest.approx(0.95)
    assert "ELEVATION" in elev.matched_terms


def test_full_outline_set_uses_fast_path():
    # The exact example from the spec: one combined schedule + two elevations.
    result = _route(
        pages=[
            ["COVER SHEET"],
            ["A-401.00", "schedule"],
            ["A-201.00", "elevation"],
            ["A-202.00", "elevation"],
            ["A-100.00", "floor plan"],
        ],
        toc=[
            (1, "A-401.00 - WINDOW, DOOR, WALL & FLOOR SCHEDULE", 2),
            (1, "A-201.00 - WEST/EAST_ELEVATION", 3),
            (1, "A-202.00 - NORTH/SOUTH_ELEVATION", 4),
        ],
    )

    assert result.confidence == "high"
    assert result.used_fast_path is True
    assert [c.page_number for c in result.schedule_candidates] == [2]
    assert result.schedule_candidates[0].role == "combined_schedule"
    assert [c.page_number for c in result.elevation_candidates] == [3, 4]


# ── Native-title (no outline) high confidence ──────────────────────────────────

def test_native_title_schedule_high_confidence():
    result = _route(
        pages=[
            ["COVER SHEET"],
            ["A-401.00 - WINDOW SCHEDULE", "W-1 36 48", "W-2 24 36"],
        ],
    )
    assert result.confidence == "high"
    assert result.used_fast_path is True
    cand = result.schedule_candidates[0]
    assert cand.page_number == 2
    assert cand.role == "window_schedule"
    assert cand.source == "native_title"
    assert cand.confidence == pytest.approx(0.95)
    assert cand.sheet_number == "A-401.00"


@pytest.mark.parametrize(
    "title, expected_role",
    [
        ("WINDOW SCHEDULE", "window_schedule"),
        ("FENESTRATION SCHEDULE", "window_schedule"),
        ("EXTERIOR DOOR SCHEDULE", "door_schedule"),
        ("INTERIOR DOOR SCHEDULE", "door_schedule"),
        ("WINDOW AND DOOR SCHEDULE", "combined_schedule"),
        ("WINDOW/DOOR SCHEDULE", "combined_schedule"),
    ],
)
def test_schedule_role_classification(title, expected_role):
    result = _route(pages=[["COVER SHEET"], [title, "some rows"]])
    assert result.schedule_candidates, f"expected a schedule candidate for {title!r}"
    assert result.schedule_candidates[0].role == expected_role


# ── Fallback (no clear candidates) ─────────────────────────────────────────────

def test_no_match_falls_back():
    result = _route(
        pages=[
            ["COVER SHEET", "PROJECT XYZ"],
            ["A-100.00", "FIRST FLOOR PLAN"],
            ["A-300.00", "BUILDING SECTION"],
        ],
    )
    assert result.confidence == "low"
    assert result.used_fast_path is False
    assert result.schedule_candidates == []
    assert result.elevation_candidates == []


# ── Drawing-list reference → medium / requires validation ──────────────────────

def test_drawing_list_reference_is_medium_confidence():
    # Page 1 is the drawing index and references A-401.00 WINDOW SCHEDULE.
    # The actual page (page 2) carries the sheet number but no page-local title.
    result = _route(
        pages=[
            ["DRAWING LIST", "A-100.00 FLOOR PLAN", "A-401.00 WINDOW SCHEDULE"],
            ["A-401.00", "SECOND FLOOR", "W-1 36 48"],  # has sheet no., no title
        ],
    )

    assert result.confidence == "medium"
    assert result.used_fast_path is False
    assert len(result.schedule_candidates) == 1

    cand = result.schedule_candidates[0]
    assert cand.page_number == 2
    assert cand.source == "drawing_list"
    assert cand.role == "window_schedule"
    assert cand.confidence == pytest.approx(0.75)
    assert any("requires validation" in w.lower() for w in result.warnings)


# ── Project info ────────────────────────────────────────────────────────────────

def test_project_info_always_includes_page_one():
    result = _route(
        pages=[
            ["some sheet", "no obvious title"],
            ["A-401.00 - WINDOW SCHEDULE", "rows"],
            ["GENERAL NOTES", "lots of notes"],
        ],
    )
    pi_pages = [c.page_number for c in result.project_info_candidates]
    assert 1 in pi_pages
    assert result.project_info_candidates[0].page_number == 1
    assert result.project_info_candidates[0].source == "first_page_default"
    # GENERAL NOTES page is picked up as an additional project-info candidate.
    assert 3 in pi_pages
