"""Deterministic elevation page detection (M2).

Turns fast-router elevation candidates into ElevationPageCandidate metadata:
direction(s), scale, sheet number/title. Does NOT render pages and does NOT
call any LLM. Counting openings / tags / dimensions is explicitly out of scope.
"""

from __future__ import annotations

import re
from typing import List, Optional

import fitz  # PyMuPDF

from app.services.extraction.pdf._helpers import (
    log_debug,
    log_section,
    normalize_for_matching,
)
from app.services.extraction.pdf.fast_page_router import RoutedPage
from app.services.extraction.pdf.schemas import ElevationPageCandidate


# Direction words → normalized lowercase. Scanned against NORMALIZED text so
# combined names like "WEST/EAST_ELEVATION" (→ "WEST EAST ELEVATION") and
# "EAST & WEST ELEVATION" (→ "EAST AND WEST ELEVATION") both parse cleanly.
DIRECTION_WORDS = {
    "EAST": "east",
    "WEST": "west",
    "NORTH": "north",
    "SOUTH": "south",
    "FRONT": "front",
    "REAR": "rear",
    "LEFT": "left",
    "RIGHT": "right",
}

_DIRECTION_RE = re.compile(r"\b(" + "|".join(DIRECTION_WORDS.keys()) + r")\b")

# Architectural scale like 3/32" = 1'-0", 1/8" = 1'-0", 3/16" = 1'-0".
# Run on RAW text (normalization strips the quote/equals characters).
_SCALE_RE = re.compile(
    r"""(\d+(?:\s*/\s*\d+)?)         # 3 or 3/32
        \s*["”″]?               # optional inch mark
        \s*=\s*
        (\d+)\s*['’′]           # feet
        \s*-?\s*
        (\d+)\s*["”″]?          # inches
    """,
    re.VERBOSE,
)

_AS_NOTED_RE = re.compile(r"\bAS\s+NOTED\b", re.IGNORECASE)

# Sheet number like A-201.00 / A201 (used only as a fallback).
_SHEET_NUMBER_RE = re.compile(r"\b[A-Z]{1,3}[-\s]?\d{1,3}(?:\.\d+)?\b")


def extract_directions(text: Optional[str]) -> List[str]:
    """Ordered, de-duplicated lowercase directions found in `text`."""
    if not text:
        return []
    norm = normalize_for_matching(text)
    out: List[str] = []
    for m in _DIRECTION_RE.finditer(norm):
        d = DIRECTION_WORDS[m.group(1)]
        if d not in out:
            out.append(d)
    return out


def extract_scale(text: Optional[str]) -> Optional[str]:
    """Extract architectural scale. A specific scale wins over 'AS NOTED'."""
    if not text:
        return None
    m = _SCALE_RE.search(text)
    if m:
        frac = re.sub(r"\s+", "", m.group(1))
        return f"{frac}\" = {m.group(2)}'-{m.group(3)}\""
    if _AS_NOTED_RE.search(text):
        return "AS NOTED"
    return None


def _extract_sheet_number(text: Optional[str]) -> Optional[str]:
    if not text:
        return None
    m = _SHEET_NUMBER_RE.search(normalize_for_matching(text))
    return m.group(0).strip() if m else None


class PDFElevationDetector:
    """Builds ElevationPageCandidate metadata from fast-router candidates."""

    def detect(
        self,
        doc: fitz.Document,
        elevation_candidates: List[RoutedPage],
        outline_titles_by_page: Optional[dict] = None,
    ) -> List[ElevationPageCandidate]:
        log_section("E1. Deterministic elevation page detection")

        if not elevation_candidates:
            log_debug("No elevation candidates from fast router; nothing to detect.")
            return []

        results: List[ElevationPageCandidate] = []
        for rp in elevation_candidates:
            page = doc[rp.page_index]
            raw_text = page.get_text("text", sort=True) or ""

            sheet_title = rp.sheet_title
            # Directions from the (concise) sheet title first; fall back to text.
            directions = extract_directions(sheet_title)
            if not directions:
                directions = extract_directions(raw_text[:1500])

            scale = extract_scale(raw_text)
            sheet_number = rp.sheet_number or _extract_sheet_number(sheet_title) or _extract_sheet_number(raw_text)

            cand = ElevationPageCandidate(
                page_index=rp.page_index,
                page_number=rp.page_number,
                sheet_number=sheet_number,
                sheet_title=sheet_title,
                directions=directions,
                scale=scale,
                source=rp.source,
                confidence=rp.confidence,
                reason=f"fast_router[{rp.source}] elevation; terms={rp.matched_terms}",
            )
            results.append(cand)

            log_debug(
                f"Elevation page {cand.page_number}: sheet={cand.sheet_number}, "
                f"directions={cand.directions}, scale={cand.scale!r}, "
                f"source={cand.source}, confidence={cand.confidence}"
            )

        return results
