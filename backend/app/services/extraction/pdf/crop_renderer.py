"""Iterates over crop plans and renders each region deterministically.

Ported verbatim from `render_crops_from_plans` in NOTEBOOKS/pdf_algo_test.py.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List

import fitz  # PyMuPDF

from app.services.extraction.pdf._helpers import log_debug, log_section
from app.services.extraction.pdf.config import PDFExtractionConfig
from app.services.extraction.pdf.models import CropPlanDebug, CropRender, PageAnalysis
from app.services.extraction.pdf.renderer import PDFRenderer
from app.services.extraction.pdf.schemas import CropRegionPlan


class PDFCropRenderer:
    def __init__(self, config: PDFExtractionConfig, renderer: PDFRenderer):
        self.config = config
        self.renderer = renderer

    def render_from_plans(
        self,
        doc: fitz.Document,
        selected_pages: List[PageAnalysis],
        crop_plans: List[CropPlanDebug],
        out_dir: Path,
    ) -> List[CropRender]:
        log_section("5. Deterministic crop execution")

        pages_by_number: Dict[int, PageAnalysis] = {p.page_number: p for p in selected_pages}
        crop_renders: List[CropRender] = []

        for plan in crop_plans:
            page_analysis = pages_by_number.get(plan.page_number)
            if not page_analysis:
                log_debug(f"Skipping crop plan for page {plan.page_number}: page not in selected candidates.")
                continue

            if not plan.contains_schedule:
                log_debug(f"Skipping crops for page {plan.page_number}: crop planner says not a schedule page.")
                continue

            if not plan.needs_crop:
                log_debug(f"No crop needed for page {plan.page_number}: planner says full page is readable enough.")
                continue

            raw_regions = plan.crop_regions[: self.config.max_crop_regions_per_page]
            if not raw_regions:
                log_debug(f"Planner requested crop for page {plan.page_number}, but returned no crop regions.")
                continue

            for idx, raw_region in enumerate(raw_regions, start=1):
                try:
                    crop_region = CropRegionPlan(**raw_region)
                except Exception as exc:
                    log_debug(f"Invalid crop region schema on page {plan.page_number} crop {idx}: {exc}")
                    continue

                crop_render = self.renderer.render_crop(
                    doc=doc,
                    page_analysis=page_analysis,
                    crop_plan=crop_region,
                    crop_index=idx,
                    out_dir=out_dir,
                )
                if crop_render:
                    crop_renders.append(crop_render)

        if not crop_renders:
            log_debug("No crops were rendered.")

        return crop_renders
