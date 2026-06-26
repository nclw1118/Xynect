"""LLM elevation crop-planning agent (M2).

A structured vision call, separate from the schedule crop_planner. Given a
full-page image + native text + deterministic elevation metadata, it returns
one normalized crop region per directional building elevation on the page.

It does NOT count openings, extract tags, read schedule rows, or check
dimensions — it only locates elevation drawing regions.
"""

from __future__ import annotations

import json
from typing import List, Optional

from app.services.extraction.pdf._helpers import log_debug, log_section
from app.services.extraction.pdf.config import PDFExtractionConfig
from app.services.extraction.pdf.llm_client import LangChainLLMClient
from app.services.extraction.pdf.models import RenderedPage
from app.services.extraction.pdf.schemas import (
    ELEVATION_DIRECTIONS,
    ElevationCropPlanResponse,
    ElevationPageCandidate,
)

MAX_ELEVATION_REGIONS_PER_PAGE = 4
_MAX_NATIVE_CHARS = 50000


def build_elevation_crop_prompt(
    candidate: ElevationPageCandidate,
    native_text: str,
) -> str:
    native_text = native_text or ""
    if len(native_text) > _MAX_NATIVE_CHARS:
        native_text = native_text[:_MAX_NATIVE_CHARS] + "\n\n[TRUNCATED: native text exceeded cap]"

    meta = {
        "page_number": candidate.page_number,
        "sheet_number": candidate.sheet_number,
        "sheet_title": candidate.sheet_title,
        "expected_directions": candidate.directions,
        "known_scale": candidate.scale,
    }

    return f"""
You are an elevation crop-planning agent for architectural PDF pages.

You receive:
1. One full-page high-resolution image of an architectural sheet.
2. Native text extracted by PyMuPDF from the same page.
3. Deterministic metadata about the page (sheet number, expected directions, scale).

Your ONLY job: locate the building ELEVATION drawing region(s) on this page and
return one crop region per directional elevation.

Rules:
- Find only building elevation drawing regions (the orthographic views of the
  building's exterior faces).
- If the page contains multiple elevations, return ONE crop per directional
  elevation (e.g. a page titled "WEST/EAST ELEVATION" usually has two drawings).
- EXCLUDE the title block, sheet border, notes, schedules, floor plans,
  sections, details, legends, key plans, and general text blocks.
- Use normalized bbox [x0, y0, x1, y1], each value between 0 and 1, with the
  top-left of the page as the origin (x0,y0 = top-left; x1,y1 = bottom-right).
- direction MUST be one of: {", ".join(ELEVATION_DIRECTIONS)}.
  Use the expected_directions metadata to help label each region; if a region's
  direction is genuinely unclear, use "unknown".
- Capture/preserve the scale string for each elevation if visible; otherwise use
  the known_scale metadata when appropriate.
- Do NOT count doors or windows. Do NOT extract tags. Do NOT extract schedule
  rows. Do NOT perform any dimension checking.
- Return at most {MAX_ELEVATION_REGIONS_PER_PAGE} regions.
- If you are unsure whether a region is an elevation, return it with a LOWER
  confidence and add a short warning, rather than inventing a region. If the
  page has no elevation drawing at all, set contains_elevation=false and return
  an empty elevation_regions list.

Set page_number = {candidate.page_number} in your response.

Deterministic metadata:
{json.dumps(meta, indent=2)}

Native text:
--- BEGIN NATIVE TEXT ---
{native_text}
--- END NATIVE TEXT ---
""".strip()


class PDFElevationCropPlanner:
    def __init__(self, config: PDFExtractionConfig, llm_client: LangChainLLMClient):
        self.config = config
        self.llm = llm_client

    def plan(
        self,
        candidate: ElevationPageCandidate,
        rendered_page: RenderedPage,
        native_text: str,
    ) -> ElevationCropPlanResponse:
        log_section(f"E2. Elevation crop planning (page {candidate.page_number})")

        structured_llm = self.llm.with_structured_output(ElevationCropPlanResponse)
        prompt = build_elevation_crop_prompt(candidate, native_text)

        log_debug(
            f"Elevation crop-planning page {candidate.page_number} with model={self.llm.model_name}, "
            f"expected_directions={candidate.directions}"
        )

        response: ElevationCropPlanResponse = self.llm.invoke_multimodal(
            structured_llm=structured_llm,
            prompt=prompt,
            image_data_uris=[rendered_page.data_uri],
        )

        # Deterministic post-processing: stamp page identity, normalize the
        # direction label, and backfill scale/sheet from the candidate metadata.
        regions = response.elevation_regions[:MAX_ELEVATION_REGIONS_PER_PAGE]
        for region in regions:
            region.page_index = candidate.page_index
            region.page_number = candidate.page_number
            if not region.sheet_number:
                region.sheet_number = candidate.sheet_number
            direction = (region.direction or "").strip().lower()
            region.direction = direction if direction in ELEVATION_DIRECTIONS else "unknown"
            if not region.scale and candidate.scale:
                region.scale = candidate.scale
        response.elevation_regions = regions
        response.page_number = candidate.page_number

        log_debug(
            f"Elevation crop plan page {response.page_number}: contains_elevation={response.contains_elevation}, "
            f"regions={len(response.elevation_regions)}, "
            f"directions={[r.direction for r in response.elevation_regions]}"
        )
        if response.warnings:
            log_debug(f"  warnings={response.warnings}")

        return response
