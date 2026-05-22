"""Project-information extraction for PDF cover/title/general-notes pages.

Runs BEFORE schedule crop planning. Sends full-page images + native text to
the LLM with a strict no-hallucinate prompt. Does not crop, does not depend on
schedule candidates.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

from app.services.extraction.pdf._helpers import log_debug, log_section
from app.services.extraction.pdf.config import PDFExtractionConfig
from app.services.extraction.pdf.llm_client import LangChainLLMClient
from app.services.extraction.pdf.models import PageAnalysis, RenderedPage
from app.services.extraction.pdf.schemas import ProjectInfoResponse


# Deterministic signals for project-info pages. Matched against the normalized
# title candidates and the upper-cased native text head.
PROJECT_INFO_KEYWORDS: List[str] = [
    "COVER",
    "TITLE SHEET",
    "GENERAL INFORMATION",
    "GENERAL NOTES",
    "PROJECT INFORMATION",
    "PROJECT DATA",
    "CODE SUMMARY",
    "SHEET INDEX",
    "INDEX OF DRAWINGS",
]

MAX_PROJECT_INFO_PAGES = 3
MAX_NATIVE_TEXT_CHARS_PER_PAGE = 30000


def build_project_info_prompt(pages: List[PageAnalysis]) -> str:
    text_blocks: List[str] = []
    for p in pages:
        text = p.text or ""
        if len(text) > MAX_NATIVE_TEXT_CHARS_PER_PAGE:
            text = text[:MAX_NATIVE_TEXT_CHARS_PER_PAGE] + "\n\n[TRUNCATED: native text exceeded cap]"
        text_blocks.append(
            f"--- BEGIN PAGE {p.page_number} NATIVE TEXT ---\n"
            f"{text}\n"
            f"--- END PAGE {p.page_number} NATIVE TEXT ---"
        )
    native_text_section = "\n\n".join(text_blocks) if text_blocks else "(no native text)"

    return f"""
You are a strict project-information extraction agent for architectural PDF cover sheets, title blocks, and general project information sections.

You receive:
1. Native text extracted by PyMuPDF from one or more project-information candidate pages.
2. Full-page high-resolution images of those same pages.

Your task:
A. Read the title block, cover sheet, project information section, and general notes.
B. Extract only clearly visible project-level metadata.
C. Return empty strings for fields you cannot verify.

Fields to extract:
- project_name: Project or building name (e.g., "Riverside Apartments").
- site_address: Street address only (e.g., "1234 Main Street"). Do not include city/state/zip here.
- city: City name only.
- state: Two-letter US state code if explicitly visible (e.g., "NY", "FL"). Empty otherwise.
- zip_code: Postal code only.

Rules:
- Do NOT hallucinate. Do NOT infer or guess values.
- If a value is not explicitly visible in the text or images, return an empty string "" for that field.
- Do not return placeholders such as "N/A", "TBD", "Unknown", or "-". Use empty strings instead.
- Prefer values from the title block over values mentioned in body text or notes.
- Trim whitespace.
- Do not include surrounding labels like "PROJECT:", "ADDRESS:", "OWNER:" in any field value.
- If the same field has conflicting values across pages, prefer the most authoritative source (title block > cover sheet > notes).
- Do not include door schedule, window schedule, or sheet titles as the project name.

Candidate page numbers: {[p.page_number for p in pages]}

Native text:
{native_text_section}
""".strip()


class PDFProjectInfoExtractor:
    def __init__(self, config: PDFExtractionConfig, llm_client: LangChainLLMClient):
        self.config = config
        self.llm = llm_client

    # ── Page selection ────────────────────────────────────────────────────────

    def select_pages(self, analyses: List[PageAnalysis]) -> List[PageAnalysis]:
        log_section("1b. Selecting project-information candidate pages")

        if not analyses:
            return []

        selected: List[PageAnalysis] = []
        seen: set[int] = set()

        # Always consider page 1 — most PDFs put the title block / cover there.
        first = analyses[0]
        selected.append(first)
        seen.add(first.page_index)
        log_debug(f"Project info page 1 always included: page_number={first.page_number}")

        # Add additional pages matching info keywords until cap is reached.
        for p in analyses:
            if p.page_index in seen:
                continue
            title_blob = " ".join(p.title_candidates)
            text_blob = (p.text or "")[:1500].upper()
            haystack = f"{title_blob} {text_blob}"
            matched = next((k for k in PROJECT_INFO_KEYWORDS if k in haystack), None)
            if matched:
                selected.append(p)
                seen.add(p.page_index)
                log_debug(
                    f"Project info page matched on '{matched}': page_number={p.page_number}"
                )
            if len(selected) >= MAX_PROJECT_INFO_PAGES:
                break

        return selected

    # ── LLM extraction ────────────────────────────────────────────────────────

    def extract(
        self,
        selected_pages: List[PageAnalysis],
        rendered_pages: List[RenderedPage],
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Run the project-info LLM call.

        Returns (project_info_dict_for_db, raw_response_for_debug).
        project_info_dict_for_db uses None for empty fields so it lines up
        with the existing _save_project_info(dict) consumer.
        """
        log_section("1c. LangChain project-information extraction")

        if not selected_pages or not rendered_pages:
            log_debug("No project-info pages selected; skipping LLM call.")
            return {}, {}

        rendered_by_page_index = {rp.page_index: rp for rp in rendered_pages}
        ordered_pages: List[PageAnalysis] = []
        image_uris: List[str] = []
        for page_analysis in selected_pages:
            rp = rendered_by_page_index.get(page_analysis.page_index)
            if not rp:
                continue
            ordered_pages.append(page_analysis)
            image_uris.append(rp.data_uri)

        if not ordered_pages or not image_uris:
            log_debug("No rendered project-info pages available; skipping LLM call.")
            return {}, {}

        prompt = build_project_info_prompt(ordered_pages)
        structured_llm = self.llm.with_structured_output(ProjectInfoResponse)

        log_debug(
            f"Project info extraction with model={self.llm.model_name}, "
            f"pages={[p.page_number for p in ordered_pages]}, images={len(image_uris)}"
        )

        response: ProjectInfoResponse = self.llm.invoke_multimodal(
            structured_llm=structured_llm,
            prompt=prompt,
            image_data_uris=image_uris,
        )

        raw = response.model_dump()

        # Convert empty strings to None so the DB row stores NULL instead of "".
        info_dict: Dict[str, Any] = {}
        for key, value in raw.items():
            cleaned = value.strip() if isinstance(value, str) else value
            info_dict[key] = cleaned if cleaned else None

        log_debug(
            f"Project info extracted: project_name={info_dict.get('project_name')!r}, "
            f"city={info_dict.get('city')!r}, state={info_dict.get('state')!r}, "
            f"zip={info_dict.get('zip_code')!r}"
        )

        return info_dict, raw
