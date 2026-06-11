"""LLM step 1: crop-planning / readability agent.

Prompt and request shape preserved verbatim from NOTEBOOKS/pdf_algo_test.py.
"""

from __future__ import annotations

import json
from typing import List

from app.services.extraction.pdf._helpers import log_debug, log_section
from app.services.extraction.pdf.config import PDFExtractionConfig
from app.services.extraction.pdf.llm_client import LangChainLLMClient
from app.services.extraction.pdf.models import CropPlanDebug, PageAnalysis, RenderedPage
from app.services.extraction.pdf.schemas import CropPlanResponse


def build_crop_planning_prompt(page_analysis: PageAnalysis) -> str:
    native_text = page_analysis.text or ""
    max_native_chars = 50000
    if len(native_text) > max_native_chars:
        native_text = native_text[:max_native_chars] + "\n\n[TRUNCATED: native text exceeded cap]"

    deterministic_debug = {
        "page_number": page_analysis.page_number,
        "title_source": page_analysis.title_source,
        "outline_titles": page_analysis.outline_titles,
        "heuristic_titles": page_analysis.heuristic_titles,
        "title_candidates": page_analysis.title_candidates,
        "sheet_number_candidates": page_analysis.sheet_number_candidates,
        "title_score": page_analysis.title_score,
        "native_text_score": page_analysis.native_text_score,
        "final_score": page_analysis.final_score,
        "selection_reason": page_analysis.selection_reason,
        "positive_signals": page_analysis.positive_signals,
        "negative_signals": page_analysis.negative_signals,
    }

    return f"""
You are a crop-planning and readability agent for architectural PDF schedule extraction.

You receive:
1. Native text extracted by PyMuPDF.
2. One full-page high-resolution image of the same PDF page.

Your jobs:
A. Decide whether this page actually contains a window/opening/glazing/fenestration schedule or a relevant mixed door/window schedule.
B. Decide whether the full-page image is readable enough to extract the table accurately without cropping.
C. If it is NOT readable enough, propose one or more crop regions using normalized coordinates.

Important:
- Only propose crops if this page is actually relevant.
- Do not crop irrelevant pages.
- Do not extract schedule rows here. This is only crop planning.
- Use normalized coordinates [x0, y0, x1, y1].
- x0/y0 are top-left; x1/y1 are bottom-right.
- Coordinates must be between 0 and 1.
- The crop should generously include the whole schedule table, including headers and all rows.
- If uncertain, make the crop slightly larger, not smaller.
- Prefer one crop around the main table. Use multiple crops only if the schedule is split into separated regions.
- If the full page is clear enough, set can_extract_without_crop=true, needs_crop=false, crop_regions=[].
- If the page is not relevant, set contains_schedule=false, needs_crop=false, crop_regions=[].

Readability labels:
- clear_enough
- too_small
- blurry
- partial
- not_readable
- unknown

Schedule type labels:
- window_schedule
- opening_schedule
- glazing_schedule
- fenestration_schedule
- mixed_door_window_schedule
- door_only_schedule
- elevation_with_window_info
- not_relevant
- unknown

Deterministic pre-analysis:
{json.dumps(deterministic_debug, indent=2)}

Native text:
--- BEGIN NATIVE TEXT ---
{native_text}
--- END NATIVE TEXT ---
""".strip()


class PDFCropPlanner:
    def __init__(self, config: PDFExtractionConfig, llm_client: LangChainLLMClient):
        self.config = config
        self.llm = llm_client

    def plan(
        self,
        selected_pages: List[PageAnalysis],
        rendered_pages: List[RenderedPage],
    ) -> List[CropPlanDebug]:
        log_section("4. LangChain crop-planning / readability agent")

        structured_llm = self.llm.with_structured_output(CropPlanResponse)
        rendered_by_page_index = {rp.page_index: rp for rp in rendered_pages}

        crop_plans: List[CropPlanDebug] = []

        for page_analysis in selected_pages:
            rendered = rendered_by_page_index[page_analysis.page_index]
            prompt = build_crop_planning_prompt(page_analysis)

            log_debug(
                f"Crop-planning page {page_analysis.page_number} with LangChain model={self.llm.model_name}"
            )
            response: CropPlanResponse = self.llm.invoke_multimodal(
                structured_llm=structured_llm,
                prompt=prompt,
                image_data_uris=[rendered.data_uri],
            )

            plan = CropPlanDebug(
                page_number=response.page_number,
                contains_schedule=response.contains_schedule,
                schedule_type=response.schedule_type,
                readability=response.readability,
                can_extract_without_crop=response.can_extract_without_crop,
                needs_crop=response.needs_crop,
                crop_regions=[r.model_dump() for r in response.crop_regions],
                confidence=response.confidence,
                reason=response.reason,
                warnings=response.warnings,
            )
            crop_plans.append(plan)

            log_debug(
                f"Crop plan page {plan.page_number}: contains_schedule={plan.contains_schedule}, "
                f"readability={plan.readability}, can_extract_without_crop={plan.can_extract_without_crop}, "
                f"needs_crop={plan.needs_crop}, crop_regions={len(plan.crop_regions)}"
            )
            log_debug(f"  reason={plan.reason}")
            if plan.warnings:
                log_debug(f"  warnings={plan.warnings}")

        return crop_plans
