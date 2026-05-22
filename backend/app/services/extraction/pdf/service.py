"""PDF extraction service — top-level orchestrator.

Equivalent to `extract_pdf()` in NOTEBOOKS/pdf_algo_test.py, refactored into
an object-oriented composition of the extraction stages. Algorithm behavior,
prompts, scoring rules, crop logic, and row normalization are preserved.

Returns the existing `ExtractionResult` consumed by the extraction agent so
the rest of the persistence pipeline (project info, window items, progress)
is unchanged.
"""

from __future__ import annotations

import io
from dataclasses import asdict
from typing import Dict, List

import fitz  # PyMuPDF

from app.services.extraction.pdf._helpers import (
    log_debug,
    log_section,
    preview_text,
)
from app.services.extraction.pdf.candidate_selector import PDFCandidateSelector
from app.services.extraction.pdf.config import PDFExtractionConfig
from app.services.extraction.pdf.crop_planner import PDFCropPlanner
from app.services.extraction.pdf.crop_renderer import PDFCropRenderer
from app.services.extraction.pdf.debug_writer import PDFExtractionDebugWriter
from app.services.extraction.pdf.llm_client import LangChainLLMClient
from app.services.extraction.pdf.models import PDFExtractionArtifacts
from app.services.extraction.pdf.page_analyzer import PDFPageAnalyzer
from app.services.extraction.pdf.project_info_extractor import PDFProjectInfoExtractor
from app.services.extraction.pdf.renderer import PDFRenderer
from app.services.extraction.pdf.row_normalizer import PDFRowNormalizer
from app.services.extraction.pdf.schedule_extractor import PDFScheduleExtractor
from app.services.extraction.progress_reporter import ProgressReporter
from app.services.extraction.spreadsheet_parser import ExtractionResult


# Progress-step labels used by this service. Kept here so the orchestrator can
# pre-register them in order.
STEP_ANALYZE = "Analyzing PDF pages"
STEP_PROJECT_INFO_SELECT = "Selecting project info pages"
STEP_PROJECT_INFO_EXTRACT = "Extracting project information"
STEP_SELECT = "Selecting candidate pages"
STEP_RENDER = "Rendering document pages"
STEP_PLAN_CROPS = "Planning crop regions"
STEP_EXTRACT = "Extracting window schedule"
STEP_NORMALIZE = "Normalizing extracted data"
STEP_SAVE = "Saving extracted rows"

STEP_NAMES_IN_ORDER: List[str] = [
    STEP_ANALYZE,
    STEP_PROJECT_INFO_SELECT,
    STEP_PROJECT_INFO_EXTRACT,
    STEP_SELECT,
    STEP_RENDER,
    STEP_PLAN_CROPS,
    STEP_EXTRACT,
    STEP_NORMALIZE,
    STEP_SAVE,
]


class PDFExtractionService:
    def __init__(self, config: PDFExtractionConfig):
        self.config = config

    def run(
        self,
        content: bytes,
        file_type: str,
        session_id: str,
        progress: ProgressReporter,
    ) -> ExtractionResult:
        """Run the LangChain crop-planning extraction. Returns an ExtractionResult."""

        log_section("PDF Extraction Service Started")
        log_debug(f"session_id={session_id}, file_type={file_type}")
        log_debug(f"Model: {self.config.llm_model}")
        log_debug(f"Full-page render DPI: {self.config.render_dpi}")
        log_debug(f"Crop render DPI: {self.config.crop_dpi}")

        warnings: List[str] = []
        debug_trace: Dict = {
            "database_used": True,
            "spreadsheet_handling_used": False,
            "image_upload_handling_used": False,
            "classification_method": "pdf_outline_titles_first_then_heuristic_titles_then_native_text_score",
            "llm_framework": "langchain",
            "chain": "candidate_page_selection -> crop_planning_agent -> deterministic_crop_renderer -> final_extraction_agent",
            "llm_input_crop_planning": "native_text_plus_full_page_high_resolution_png",
            "llm_input_final_extraction": "native_text_plus_full_page_png_plus_optional_zoomed_crops",
            "rendering_policy": (
                "full page PNG for context; LLM-planned normalized bboxes rendered as "
                "high-DPI crops; overlay images saved for debug"
            ),
        }

        debug_writer = PDFExtractionDebugWriter(self.config)
        out_dir = debug_writer.ensure_session_dir(session_id)
        debug_trace["debug_output_dir"] = str(out_dir)

        doc = fitz.open(stream=io.BytesIO(content), filetype="pdf")
        try:
            page_count = doc.page_count
            debug_trace["file_type"] = file_type
            debug_trace["page_count"] = page_count
            log_debug(f"Detected file_type={file_type}, page_count={page_count}")

            # ── Stage 1: outline + per-page analysis ──────────────────────────
            progress.start(STEP_ANALYZE)
            analyzer = PDFPageAnalyzer()
            outline_titles_by_page = analyzer.extract_outline_titles(doc)
            debug_trace["outline_title_pages_found"] = sorted(
                [idx + 1 for idx in outline_titles_by_page.keys()]
            )
            debug_trace["outline_title_count"] = sum(
                len(v) for v in outline_titles_by_page.values()
            )
            analyses = analyzer.analyze(doc, outline_titles_by_page)
            progress.complete(STEP_ANALYZE)

            # Renderer + LLM client are shared by project-info extraction and
            # downstream schedule extraction. Initialize once, here, so an
            # invalid API key fails fast before we burn time rendering pages.
            renderer = PDFRenderer(self.config)
            llm_client = LangChainLLMClient(self.config)

            # ── Stage 1b: select project-info pages ───────────────────────────
            progress.start(STEP_PROJECT_INFO_SELECT)
            pi_extractor = PDFProjectInfoExtractor(self.config, llm_client)
            project_info_pages = pi_extractor.select_pages(analyses)
            progress.complete(STEP_PROJECT_INFO_SELECT)

            # ── Stage 1c: extract project information ─────────────────────────
            progress.start(STEP_PROJECT_INFO_EXTRACT)
            project_info_dict: Dict | None = None
            project_info_raw: Dict = {}
            project_info_rendered_pages: List = []
            if project_info_pages:
                project_info_rendered_pages = renderer.render_selected_pages(
                    doc, project_info_pages, out_dir
                )
                project_info_dict, project_info_raw = pi_extractor.extract(
                    project_info_pages, project_info_rendered_pages
                )
            progress.complete(STEP_PROJECT_INFO_EXTRACT)

            # ── Stage 2: candidate selection ──────────────────────────────────
            progress.start(STEP_SELECT)
            selector = PDFCandidateSelector(self.config)
            selected_pages = selector.select(analyses, page_count)
            progress.complete(STEP_SELECT)

            # ── Stage 3: full-page render ─────────────────────────────────────
            progress.start(STEP_RENDER)
            rendered_pages = renderer.render_selected_pages(doc, selected_pages, out_dir)
            progress.complete(STEP_RENDER)

            # ── Stage 4: LLM crop planning ────────────────────────────────────
            progress.start(STEP_PLAN_CROPS)
            crop_planner = PDFCropPlanner(self.config, llm_client)
            crop_plans = crop_planner.plan(selected_pages, rendered_pages)
            progress.complete(STEP_PLAN_CROPS)

            # ── Stage 5: deterministic crop render + LLM extraction ───────────
            progress.start(STEP_EXTRACT)
            crop_renderer = PDFCropRenderer(self.config, renderer)
            crop_renders = crop_renderer.render_from_plans(doc, selected_pages, crop_plans, out_dir)
            extractor = PDFScheduleExtractor(self.config, llm_client)
            llm_results = extractor.extract(selected_pages, rendered_pages, crop_plans, crop_renders)
            progress.complete(STEP_EXTRACT)

            # ── Stage 6: normalize ────────────────────────────────────────────
            progress.start(STEP_NORMALIZE)
            normalizer = PDFRowNormalizer()
            extracted_rows = normalizer.merge_and_normalize(llm_results)

            # Apply deterministic area calculation (same policy as existing flow:
            # area is never trusted from the LLM).
            from app.services.extraction.normalizers import calculate_area
            for row in extracted_rows:
                if not row.get("area"):
                    computed = calculate_area(row.get("width"), row.get("height"))
                    if computed:
                        row["area"] = computed
            progress.complete(STEP_NORMALIZE)

            if not extracted_rows:
                warnings.append(
                    "No window/opening schedule rows were extracted from selected candidate pages."
                )

            # ── Debug artifacts ───────────────────────────────────────────────
            candidate_pages_dict = []
            for p in analyses:
                candidate_pages_dict.append({
                    "page_index": p.page_index,
                    "page_number": p.page_number,
                    "text_length": p.text_length,
                    "title_source": p.title_source,
                    "outline_titles": p.outline_titles,
                    "heuristic_titles": p.heuristic_titles,
                    "title_candidates": p.title_candidates,
                    "sheet_number_candidates": p.sheet_number_candidates,
                    "title_score": p.title_score,
                    "native_text_score": p.native_text_score,
                    "final_score": p.final_score,
                    "selected": p.selected,
                    "selection_reason": p.selection_reason,
                    "positive_signals": p.positive_signals,
                    "negative_signals": p.negative_signals,
                    "native_text_preview": preview_text(p.text),
                })

            rendered_pages_dict = [
                {
                    "page_index": rp.page_index,
                    "page_number": rp.page_number,
                    "png_path": rp.png_path,
                    "width_px": rp.width_px,
                    "height_px": rp.height_px,
                    "dpi": rp.dpi,
                }
                for rp in rendered_pages
            ]

            crop_plans_dict = [asdict(cp) for cp in crop_plans]
            crop_renders_dict = [
                {
                    "page_index": cr.page_index,
                    "page_number": cr.page_number,
                    "crop_index": cr.crop_index,
                    "label": cr.label,
                    "method": cr.method,
                    "normalized_bbox_original": cr.normalized_bbox_original,
                    "normalized_bbox_expanded": cr.normalized_bbox_expanded,
                    "pdf_rect_points": cr.pdf_rect_points,
                    "png_path": cr.png_path,
                    "overlay_path": cr.overlay_path,
                    "width_px": cr.width_px,
                    "height_px": cr.height_px,
                    "dpi": cr.dpi,
                    "confidence": cr.confidence,
                    "reason": cr.reason,
                }
                for cr in crop_renders
            ]

            llm_results_dict = [
                {
                    "page_number": r.page_number,
                    "contains_schedule": r.contains_schedule,
                    "schedule_type": r.schedule_type,
                    "confidence": r.confidence,
                    "reason": r.reason,
                    "rows_extracted": len(r.extracted_rows),
                    "warnings": r.warnings,
                    "raw_response": r.raw_response,
                }
                for r in llm_results
            ]

            outline_titles_by_page_json = {
                str(idx + 1): titles for idx, titles in sorted(outline_titles_by_page.items())
            }

            debug_trace["selected_page_numbers"] = [p.page_number for p in selected_pages]
            debug_trace["rendered_page_numbers"] = [rp.page_number for rp in rendered_pages]
            debug_trace["crop_plan_pages"] = [cp.page_number for cp in crop_plans]
            debug_trace["crop_render_count"] = len(crop_renders)
            debug_trace["crop_render_pages"] = [cr.page_number for cr in crop_renders]
            debug_trace["llm_page_numbers"] = [r.page_number for r in llm_results]
            debug_trace["rows_extracted_count"] = len(extracted_rows)
            debug_trace["project_info_page_numbers"] = [p.page_number for p in project_info_pages]

            project_info_artifact: Dict = {
                "selected_pages": [p.page_number for p in project_info_pages],
                "rendered_pages": [rp.page_number for rp in project_info_rendered_pages],
                "extracted": project_info_dict or {},
                "raw_response": project_info_raw,
            }

            artifacts = PDFExtractionArtifacts(
                pdf_source=f"session:{session_id}",
                file_type=file_type,
                page_count=page_count,
                outline_titles_by_page=outline_titles_by_page_json,
                candidate_pages=candidate_pages_dict,
                rendered_pages=rendered_pages_dict,
                crop_plans=crop_plans_dict,
                crop_renders=crop_renders_dict,
                llm_results=llm_results_dict,
                extracted_window_rows=extracted_rows,
                warnings=warnings,
                debug_trace=debug_trace,
                project_info=project_info_artifact,
            )

            debug_writer.write_result(out_dir, artifacts)

            log_section("8. Final summary")
            log_debug(f"Outline/sidebar title pages found: {debug_trace.get('outline_title_pages_found', [])}")
            log_debug(f"Selected pages: {debug_trace['selected_page_numbers']}")
            log_debug(f"Rendered full pages: {debug_trace['rendered_page_numbers']}")
            log_debug(f"Crop plan pages: {debug_trace['crop_plan_pages']}")
            log_debug(
                f"Crop renders: {debug_trace['crop_render_count']} on pages "
                f"{debug_trace['crop_render_pages']}"
            )
            log_debug(f"LLM final extraction pages: {debug_trace['llm_page_numbers']}")
            log_debug(f"Rows extracted: {len(extracted_rows)}")
            if warnings:
                log_debug(f"Warnings: {warnings}")

            # ── Stage 7: mark "Saving extracted rows" active. Orchestrator
            #    completes it after DB persistence. ────────────────────────────
            progress.start(STEP_SAVE)

            return ExtractionResult(
                window_rows=extracted_rows,
                warnings=warnings,
                project_info=project_info_dict,
            )

        finally:
            doc.close()
