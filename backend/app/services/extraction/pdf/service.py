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
    close_session_log,
    log_debug,
    log_section,
    normalize_for_matching,
    open_session_log,
    preview_text,
)
from app.services.extraction.pdf.candidate_selector import PDFCandidateSelector
from app.services.extraction.pdf.config import PDFExtractionConfig
from app.services.extraction.pdf.crop_planner import PDFCropPlanner
from app.services.extraction.pdf.crop_renderer import PDFCropRenderer
from app.services.extraction.pdf.debug_writer import PDFExtractionDebugWriter
from app.services.extraction.pdf.fast_page_router import (
    FastPageRouter,
    FastPageRoutingResult,
    RoutedPage,
)
from app.services.extraction.pdf.llm_client import LangChainLLMClient
from app.services.extraction.pdf.models import PageAnalysis, PDFExtractionArtifacts
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

        # Tee all pipeline logs (log_section/log_step/log_debug) to a per-session
        # file next to the other debug artifacts, e.g.
        # storage/extraction_debug/<session_id>/extraction.log
        log_handle = open_session_log(out_dir / "extraction.log")

        doc = None
        try:
            log_section("PDF Extraction Service Started")
            log_debug(f"session_id={session_id}, file_type={file_type}")
            log_debug(f"Model: {self.config.llm_model}")
            log_debug(f"Full-page render DPI: {self.config.render_dpi}")
            log_debug(f"Crop render DPI: {self.config.crop_dpi}")
            log_debug(f"Debug output dir: {out_dir}")
            log_debug(f"Session log file: {out_dir / 'extraction.log'}")

            doc = fitz.open(stream=io.BytesIO(content), filetype="pdf")
            page_count = doc.page_count
            debug_trace["file_type"] = file_type
            debug_trace["page_count"] = page_count
            log_debug(f"Detected file_type={file_type}, page_count={page_count}")

            # ── Stage 1: outline + fast routing, then either fast path or the
            #    heavy per-page analyzer fallback ────────────────────────────────
            progress.start(STEP_ANALYZE)
            analyzer = PDFPageAnalyzer()
            outline_titles_by_page = analyzer.extract_outline_titles(doc)
            debug_trace["outline_title_pages_found"] = sorted(
                [idx + 1 for idx in outline_titles_by_page.keys()]
            )
            debug_trace["outline_title_count"] = sum(
                len(v) for v in outline_titles_by_page.values()
            )

            # Cheap deterministic routing pass (no render, no LLM). When the
            # router is highly confident we skip the heavy analyzer/selector.
            routing: FastPageRoutingResult | None = None
            use_fast_path = False
            fallback_reason: str | None = None
            analyses: List[PageAnalysis] | None = None

            if self.config.fast_router_enabled:
                routing = FastPageRouter().route(doc, outline_titles_by_page)
                use_fast_path = routing.used_fast_path
                if not use_fast_path:
                    fallback_reason = (
                        f"fast_router_confidence={routing.confidence}; "
                        f"schedule_candidates={len(routing.schedule_candidates)}"
                    )
            else:
                fallback_reason = "fast_router_disabled"

            if use_fast_path and routing is not None:
                # Fast path: route directly to schedule candidates; skip the
                # expensive per-page analysis + candidate selection.
                selected_pages = self._routed_to_analyses(
                    doc, routing.schedule_candidates, outline_titles_by_page
                )
                log_debug(
                    f"FAST PATH: routed schedule pages "
                    f"{[p.page_number for p in selected_pages]} "
                    f"(confidence={routing.confidence}); skipping heavy analyzer/selector."
                )
            else:
                # Fallback: existing robust per-page analysis (unchanged).
                analyses = analyzer.analyze(doc, outline_titles_by_page)
                if fallback_reason:
                    log_debug(f"FALLBACK PATH: {fallback_reason}; running heavy analyzer.")
            progress.complete(STEP_ANALYZE)

            debug_trace["fast_path_used"] = use_fast_path
            debug_trace["fallback_reason"] = fallback_reason
            if routing is not None:
                debug_trace["fast_page_routing"] = routing.to_debug_dict()
                debug_trace["elevation_candidate_page_numbers"] = [
                    c.page_number for c in routing.elevation_candidates
                ]

            # Renderer + LLM client are shared by project-info extraction and
            # downstream schedule extraction. Initialize once, here, so an
            # invalid API key fails fast before we burn time rendering pages.
            renderer = PDFRenderer(self.config)
            llm_client = LangChainLLMClient(self.config)

            # ── Stage 1b: select project-info pages ───────────────────────────
            progress.start(STEP_PROJECT_INFO_SELECT)
            pi_extractor = PDFProjectInfoExtractor(self.config, llm_client)
            if use_fast_path and routing is not None:
                # Use the router's lightweight project-info candidates so we do
                # not depend on the heavy analyzer having run.
                project_info_pages = self._routed_to_analyses(
                    doc, routing.project_info_candidates, outline_titles_by_page
                )
            else:
                project_info_pages = pi_extractor.select_pages(analyses or [])
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
            if use_fast_path:
                # selected_pages already routed in Stage 1; skip heavy selector.
                log_debug(
                    "FAST PATH: using routed schedule candidates; "
                    "skipping PDFCandidateSelector."
                )
            else:
                selector = PDFCandidateSelector(self.config)
                selected_pages = selector.select(analyses or [], page_count)
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
            extracted_door_rows = normalizer.merge_and_normalize_doors(llm_results)

            # Apply deterministic area calculation (same policy as existing flow:
            # area is never trusted from the LLM). Applied to both windows and doors.
            from app.services.extraction.normalizers import calculate_area
            for row in extracted_rows + extracted_door_rows:
                if not row.get("area"):
                    computed = calculate_area(row.get("width"), row.get("height"))
                    if computed:
                        row["area"] = computed
            progress.complete(STEP_NORMALIZE)

            if not extracted_rows:
                warnings.append(
                    "No window/opening schedule rows were extracted from selected candidate pages."
                )

            # ── Stage 6b: passive elevation branch (M2) ───────────────────────
            # Never fatal: failures are logged + recorded in elevation_regions.json
            # but must not change schedule extraction or fail the run.
            elevation_payload = self._run_elevation_branch(
                doc, routing, outline_titles_by_page, renderer, llm_client, out_dir
            )
            debug_writer.write_elevation_regions(out_dir, elevation_payload)
            debug_trace["elevation_pages"] = [p["page_number"] for p in elevation_payload["pages"]]
            debug_trace["elevation_region_count"] = len(
                [r for r in elevation_payload["regions"] if r.get("valid")]
            )

            # ── Debug artifacts ───────────────────────────────────────────────
            # In the fast path there is no full per-page analysis; fall back to
            # the routed/selected pages so the artifact stays valid.
            candidate_pages_source = analyses if analyses is not None else selected_pages
            candidate_pages_dict = []
            for p in candidate_pages_source:
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
                    "door_rows_extracted": len(r.extracted_door_rows),
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
            debug_trace["door_rows_extracted_count"] = len(extracted_door_rows)
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
                extracted_door_rows=extracted_door_rows,
                warnings=warnings,
                debug_trace=debug_trace,
                project_info=project_info_artifact,
            )

            debug_writer.write_result(out_dir, artifacts)

            # Dedicated fast-routing debug artifact.
            if routing is not None:
                routing_payload = routing.to_debug_dict()
                routing_payload["fast_path_used"] = use_fast_path
                routing_payload["fallback_reason"] = fallback_reason
                debug_writer.write_fast_routing(out_dir, routing_payload)
            else:
                debug_writer.write_fast_routing(
                    out_dir,
                    {
                        "fast_path_used": False,
                        "fallback_reason": fallback_reason,
                        "note": "Fast router disabled; heavy analyzer used.",
                    },
                )

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
            log_debug(f"Window rows extracted: {len(extracted_rows)}")
            log_debug(f"Door rows extracted: {len(extracted_door_rows)}")
            if warnings:
                log_debug(f"Warnings: {warnings}")

            # ── Stage 7: mark "Saving extracted rows" active. Orchestrator
            #    completes it after DB persistence. ────────────────────────────
            progress.start(STEP_SAVE)

            return ExtractionResult(
                window_rows=extracted_rows,
                door_rows=extracted_door_rows,
                warnings=warnings,
                project_info=project_info_dict,
            )

        finally:
            if doc is not None:
                doc.close()
            close_session_log(log_handle)

    # ── Fast-path adapter ───────────────────────────────────────────────────────

    def _routed_to_analyses(
        self,
        doc: "fitz.Document",
        routed_pages: List[RoutedPage],
        outline_titles_by_page: Dict[int, List[str]],
    ) -> List[PageAnalysis]:
        """Adapt fast-router results into the PageAnalysis objects consumed by the
        downstream render / crop-plan / extraction stages.

        Only the routed pages have their native text read here (cheap, a handful
        of pages) so the heavy whole-document analysis is avoided. Scoring fields
        are derived from the router confidence purely for debug visibility.
        """
        analyses: List[PageAnalysis] = []
        for rp in routed_pages:
            page = doc[rp.page_index]
            text = page.get_text("text", sort=True) or ""

            outline_titles = list(outline_titles_by_page.get(rp.page_index, []))
            title_candidates: List[str] = []
            if rp.sheet_title:
                title_candidates.append(normalize_for_matching(rp.sheet_title))
            for t in outline_titles:
                nt = normalize_for_matching(t)
                if nt and nt not in title_candidates:
                    title_candidates.append(nt)

            score = round(rp.confidence * 100.0, 2)
            title_source = "pdf_outline" if rp.source == "pdf_outline" else f"fast_router_{rp.source}"

            analyses.append(
                PageAnalysis(
                    page_index=rp.page_index,
                    page_number=rp.page_number,
                    text=text,
                    text_length=len(text),
                    title_candidates=title_candidates,
                    title_source=title_source,
                    outline_titles=outline_titles,
                    heuristic_titles=[],
                    sheet_number_candidates=[rp.sheet_number] if rp.sheet_number else [],
                    title_score=score,
                    native_text_score=0.0,
                    final_score=score,
                    selected=True,
                    selection_reason=(
                        f"fast_page_router[{rp.source}] role={rp.role} "
                        f"confidence={rp.confidence} terms={rp.matched_terms}"
                    ),
                    positive_signals=[f"fast_router matched: {t}" for t in rp.matched_terms],
                    negative_signals=[],
                )
            )
        return analyses

    # ── Passive elevation branch (M2) ───────────────────────────────────────────

    def _run_elevation_branch(
        self,
        doc: "fitz.Document",
        routing: FastPageRoutingResult | None,
        outline_titles_by_page: Dict[int, List[str]],
        renderer: PDFRenderer,
        llm_client: LangChainLLMClient,
        out_dir,
    ) -> Dict:
        """Detect elevation pages and plan/render directional elevation crops.

        Passive and best-effort: this method NEVER raises. Any failure is logged
        and recorded in the returned payload's warnings, so schedule extraction
        and the overall run are unaffected. It does not count openings/tags or
        check dimensions.
        """
        # Local imports keep the elevation feature self-contained and avoid any
        # import cost when there are no elevation candidates.
        from app.services.extraction.pdf.elevation_crop_planner import PDFElevationCropPlanner
        from app.services.extraction.pdf.elevation_crop_renderer import PDFElevationCropRenderer
        from app.services.extraction.pdf.elevation_detector import PDFElevationDetector

        payload: Dict = {"enabled": False, "pages": [], "regions": [], "warnings": []}
        try:
            if routing is None or not routing.elevation_candidates:
                return payload
            payload["enabled"] = True

            log_section("E. Passive elevation branch (M2)")
            candidates = PDFElevationDetector().detect(
                doc, routing.elevation_candidates, outline_titles_by_page
            )
            if not candidates:
                return payload

            elev_pages = self._routed_to_analyses(
                doc, routing.elevation_candidates, outline_titles_by_page
            )
            pa_by_index = {pa.page_index: pa for pa in elev_pages}
            rendered = renderer.render_selected_pages(doc, elev_pages, out_dir)
            rp_by_index = {rp.page_index: rp for rp in rendered}

            planner = PDFElevationCropPlanner(self.config, llm_client)
            crop_renderer = PDFElevationCropRenderer(self.config, renderer)

            for cand in candidates:
                rp = rp_by_index.get(cand.page_index)
                pa = pa_by_index.get(cand.page_index)
                if rp is None:
                    continue
                try:
                    plan = planner.plan(cand, rp, pa.text if pa else "")
                    region_dicts, overlay_path = crop_renderer.render_page_regions(
                        doc, cand, plan.elevation_regions, out_dir
                    )
                    payload["pages"].append({
                        "page_number": cand.page_number,
                        "page_index": cand.page_index,
                        "sheet_number": cand.sheet_number,
                        "sheet_title": cand.sheet_title,
                        "directions": cand.directions,
                        "scale": cand.scale,
                        "source": cand.source,
                        "confidence": cand.confidence,
                        "contains_elevation": plan.contains_elevation,
                        "region_count": len([r for r in region_dicts if r.get("valid")]),
                        "overlay_path": overlay_path,
                        "rendered_page_png": rp.png_path,
                    })
                    payload["regions"].extend(region_dicts)
                    payload["warnings"].extend(plan.warnings)
                except Exception as exc:
                    msg = f"Elevation crop planning failed for page {cand.page_number}: {exc}"
                    log_debug(msg)
                    payload["warnings"].append(msg)

            log_section("E4. Elevation branch summary")
            log_debug(f"Detected elevation pages: {[p['page_number'] for p in payload['pages']]}")
            valid_regions = [r for r in payload["regions"] if r.get("valid")]
            log_debug(f"Planned elevation regions: {len(valid_regions)}")
            for r in valid_regions:
                log_debug(f"  crop: page {r['page_number']} {r['direction']} -> {r['png_path']}")
            if payload["warnings"]:
                log_debug(f"Elevation warnings: {payload['warnings']}")
        except Exception as exc:
            msg = f"Elevation branch failed (non-fatal): {exc}"
            log_debug(msg)
            payload["warnings"].append(msg)

        return payload
