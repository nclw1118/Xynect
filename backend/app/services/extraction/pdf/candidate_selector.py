"""Candidate page selection: strong-title pages + native-text backups.

Ported verbatim from `select_candidate_pages` in NOTEBOOKS/pdf_algo_test.py.
"""

from __future__ import annotations

from typing import Dict, List

from app.services.extraction.pdf._helpers import log_debug, log_section
from app.services.extraction.pdf.config import PDFExtractionConfig
from app.services.extraction.pdf.models import PageAnalysis


class PDFCandidateSelector:
    def __init__(self, config: PDFExtractionConfig):
        self.config = config

    def select(self, analyses: List[PageAnalysis], page_count: int) -> List[PageAnalysis]:
        log_section("2. Candidate page selection")

        if page_count == 1:
            analyses[0].selected = True
            analyses[0].selection_reason = "Single-page PDF: send the only page to LLM."
            log_debug("Single-page PDF detected. Selected page 1 directly.")
            return analyses[:1]

        strong_title_pages = [
            p for p in analyses if p.title_score >= self.config.strong_title_threshold
        ]
        backup_pages = sorted(
            analyses,
            key=lambda p: p.native_text_score,
            reverse=True,
        )[: self.config.top_native_text_backup_pages]

        selected_by_index: Dict[int, PageAnalysis] = {}

        for p in strong_title_pages:
            p.selected = True
            if p.title_source == "pdf_outline":
                p.selection_reason = (
                    f"Strong PDF outline/sidebar title match: title_score={p.title_score} "
                    f">= {self.config.strong_title_threshold}."
                )
            else:
                p.selection_reason = (
                    f"Strong heuristic title match: title_score={p.title_score} "
                    f">= {self.config.strong_title_threshold}."
                )
            selected_by_index[p.page_index] = p

        for p in backup_pages:
            if p.page_index not in selected_by_index:
                p.selected = True
                p.selection_reason = (
                    f"Native-text backup candidate: native_text_score={p.native_text_score}; "
                    f"ranked in top {self.config.top_native_text_backup_pages}."
                )
                selected_by_index[p.page_index] = p

        selected = sorted(
            selected_by_index.values(),
            key=lambda p: (p.title_score, p.final_score, p.native_text_score),
            reverse=True,
        )
        selected = selected[: self.config.max_candidate_pages_sent_to_llm]

        for p in selected:
            log_debug(
                f"SELECTED page {p.page_number}: title_source={p.title_source}, final_score={p.final_score}, "
                f"title_score={p.title_score}, native_text_score={p.native_text_score}. "
                f"Reason: {p.selection_reason}"
            )

        if not selected:
            fallback = max(analyses, key=lambda p: p.final_score)
            fallback.selected = True
            fallback.selection_reason = "Fallback: no candidates selected; chose highest final score page."
            selected = [fallback]
            log_debug(f"Fallback selected page {fallback.page_number}.")

        return selected
