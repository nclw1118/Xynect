"""Deterministic per-page analysis: outline titles, heuristic titles, scoring.

All regex patterns, weights, and thresholds are preserved verbatim from
NOTEBOOKS/pdf_algo_test.py.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple

import fitz  # PyMuPDF

from app.services.extraction.pdf._helpers import (
    log_debug,
    log_section,
    normalize_for_matching,
    preview_text,
)
from app.services.extraction.pdf.models import PageAnalysis


# ── Deterministic scoring rules (verbatim from prototype) ─────────────────────

TITLE_POSITIVE_RULES: List[Tuple[str, float, str]] = [
    (r"\bWINDOW SCHEDULE\b", 100, "exact title phrase: WINDOW SCHEDULE"),
    (r"\bDOOR AND WINDOW SCHEDULE\b", 95, "exact title phrase: DOOR AND WINDOW SCHEDULE"),
    (r"\bDOOR WINDOW SCHEDULE\b", 90, "title phrase: DOOR WINDOW SCHEDULE"),
    (r"\bOPENING SCHEDULE\b", 90, "title phrase: OPENING SCHEDULE"),
    (r"\bGLAZING SCHEDULE\b", 85, "title phrase: GLAZING SCHEDULE"),
    (r"\bFENESTRATION SCHEDULE\b", 85, "title phrase: FENESTRATION SCHEDULE"),
    (r"\bEXTERIOR OPENING SCHEDULE\b", 75, "title phrase: EXTERIOR OPENING SCHEDULE"),
    (r"\bSCHEDULE\b.*\bWINDOW\b|\bWINDOW\b.*\bSCHEDULE\b", 60, "title contains SCHEDULE and WINDOW"),
    (r"\bSCHEDULE\b.*\bGLAZING\b|\bGLAZING\b.*\bSCHEDULE\b", 50, "title contains SCHEDULE and GLAZING"),
    (r"\bSCHEDULE\b", 40, "title contains SCHEDULE"),
]

TITLE_NEGATIVE_RULES: List[Tuple[str, float, str]] = [
    (r"\bFLOOR PLAN\b", -70, "negative title signal: FLOOR PLAN"),
    (r"\bROOF PLAN\b", -60, "negative title signal: ROOF PLAN"),
    (r"\bELEVATION\b", -20, "mild negative title signal: ELEVATION without schedule"),
    (r"\bSECTION\b", -50, "negative title signal: SECTION"),
    (r"\bDETAIL\b", -45, "negative title signal: DETAIL"),
    (r"\bFOUNDATION\b", -40, "negative title signal: FOUNDATION"),
    (r"\bSITE PLAN\b", -40, "negative title signal: SITE PLAN"),
    (r"\bGENERAL NOTES\b", -30, "negative title signal: GENERAL NOTES"),
]

NATIVE_POSITIVE_RULES: List[Tuple[str, float, str]] = [
    (r"\bWINDOW SCHEDULE\b", 30, "native text contains WINDOW SCHEDULE"),
    (r"\bGLAZING SCHEDULE\b", 25, "native text contains GLAZING SCHEDULE"),
    (r"\bOPENING SCHEDULE\b", 25, "native text contains OPENING SCHEDULE"),
    (r"\bFENESTRATION SCHEDULE\b", 20, "native text contains FENESTRATION SCHEDULE"),
    (r"\bU[\-\s]?VALUE\b|\bU[\-\s]?FACTOR\b", 15, "native text contains U-VALUE/U-FACTOR"),
    (r"\bSHGC\b", 15, "native text contains SHGC"),
    (r"\bVT\b|\bVISIBLE TRANSMITTANCE\b", 10, "native text contains VT/visible transmittance"),
    (r"\bWIDTH\b|\bWID\b|\bW\b", 10, "native text contains WIDTH"),
    (r"\bHEIGHT\b|\bHT\b|\bH\b", 10, "native text contains HEIGHT"),
    (r"\bQUANTITY\b|\bQTY\b", 10, "native text contains QUANTITY/QTY"),
    (r"\bTAG\b|\bMARK\b", 10, "native text contains TAG/MARK"),
    (r"\bGLASS TYPE\b|\bGLAZING TYPE\b", 10, "native text contains GLASS/GLAZING TYPE"),
    (r"\bMATERIAL\b|\bFRAME\b", 8, "native text contains MATERIAL/FRAME"),
    (r"\bAREA\b", 8, "native text contains AREA"),
]

NATIVE_NEGATIVE_RULES: List[Tuple[str, float, str]] = [
    (r"\bGENERAL NOTES\b", -20, "native text mostly likely notes"),
    (r"\bFLOOR PLAN\b", -15, "native text contains FLOOR PLAN"),
    (r"\bFOUNDATION PLAN\b", -20, "native text contains FOUNDATION PLAN"),
    (r"\bSITE PLAN\b", -20, "native text contains SITE PLAN"),
]


# ── Outline / TOC extraction ──────────────────────────────────────────────────

def extract_outline_titles(doc: fitz.Document) -> Dict[int, List[str]]:
    """Extract embedded PDF outline/sidebar/bookmark titles → {page_index: [titles]}."""
    page_titles: Dict[int, List[str]] = {}

    try:
        toc = doc.get_toc(simple=True)
    except Exception as exc:
        log_debug(f"Could not read PDF outline/bookmarks with doc.get_toc(): {exc}")
        return page_titles

    if not toc:
        return page_titles

    for item in toc:
        if len(item) < 3:
            continue

        level, title, page_number = item

        if not title or page_number is None or page_number <= 0:
            continue

        page_index = int(page_number) - 1
        if page_index < 0 or page_index >= doc.page_count:
            continue

        clean_title = re.sub(r"\s+", " ", str(title)).strip()
        if not clean_title:
            continue

        page_titles.setdefault(page_index, [])
        if clean_title not in page_titles[page_index]:
            page_titles[page_index].append(clean_title)

    return page_titles


# ── Native text + heuristic title extraction ──────────────────────────────────

def extract_native_text(page: fitz.Page) -> str:
    return page.get_text("text", sort=True) or ""


def extract_blocks_with_font_info(page: fitz.Page) -> List[Dict[str, Any]]:
    data = page.get_text("dict")
    lines: List[Dict[str, Any]] = []

    for block in data.get("blocks", []):
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            spans = line.get("spans", [])
            text = "".join(span.get("text", "") for span in spans).strip()
            if not text:
                continue
            max_size = max((span.get("size", 0) for span in spans), default=0)
            bbox = line.get("bbox", block.get("bbox", [0, 0, 0, 0]))
            lines.append({
                "text": text,
                "norm_text": normalize_for_matching(text),
                "bbox": bbox,
                "font_size": max_size,
            })

    return lines


def extract_sheet_numbers(text: str) -> List[str]:
    patterns = [
        r"\b[A-Z]{1,3}[-\s]?\d{1,3}(?:\.\d+)?\b",
        r"\b[A-Z]\d{3}\b",
    ]
    found: List[str] = []
    normalized_text = normalize_for_matching(text)
    for pattern in patterns:
        for m in re.finditer(pattern, normalized_text):
            candidate = m.group(0).strip()
            if candidate not in found:
                found.append(candidate)
    return found[:10]


def extract_title_candidates(page: fitz.Page, native_text: str) -> List[str]:
    page_rect = page.rect
    page_width = float(page_rect.width)
    page_height = float(page_rect.height)
    lines = extract_blocks_with_font_info(page)

    candidates: List[str] = []

    def add_candidate(raw: str) -> None:
        raw = re.sub(r"\s+", " ", raw).strip()
        if not raw:
            return
        norm = normalize_for_matching(raw)
        if len(norm) < 3:
            return
        if len(norm) > 90:
            return
        if norm not in candidates:
            candidates.append(norm)

    title_keywords = [
        "WINDOW", "SCHEDULE", "GLAZING", "FENESTRATION", "OPENING",
        "ELEVATION", "FLOOR PLAN", "DETAIL", "SECTION", "DOOR",
    ]
    for line in lines:
        norm = line["norm_text"]
        if any(k in norm for k in title_keywords):
            add_candidate(line["text"])

    if lines:
        sizes = sorted([ln["font_size"] for ln in lines], reverse=True)
        large_threshold = sizes[min(10, len(sizes) - 1)] if sizes else 0
        large_threshold = max(large_threshold, 10)
        for line in sorted(lines, key=lambda x: x["font_size"], reverse=True)[:20]:
            if line["font_size"] >= large_threshold:
                add_candidate(line["text"])

    for line in lines:
        x0, y0, x1, y1 = line["bbox"]
        in_bottom_band = y0 > page_height * 0.65
        in_right_band = x0 > page_width * 0.45
        if in_bottom_band or in_right_band:
            add_candidate(line["text"])

    text_lines = [normalize_for_matching(x) for x in native_text.splitlines() if x.strip()]
    for line in text_lines[:25] + text_lines[-25:]:
        add_candidate(line)

    return candidates[:30]


def choose_title_candidates(
    page_index: int,
    outline_titles_by_page: Dict[int, List[str]],
    page: fitz.Page,
    native_text: str,
) -> Tuple[List[str], str, List[str], List[str]]:
    outline_titles = outline_titles_by_page.get(page_index, [])

    if outline_titles:
        normalized_outline_titles = [normalize_for_matching(t) for t in outline_titles]
        return normalized_outline_titles, "pdf_outline", outline_titles, []

    heuristic_titles = extract_title_candidates(page, native_text)
    if heuristic_titles:
        return heuristic_titles, "heuristic_text_blocks", [], heuristic_titles

    return [], "none", [], []


# ── Scoring ───────────────────────────────────────────────────────────────────

def score_title_candidates(
    title_candidates: List[str],
    title_source: str = "heuristic_text_blocks",
) -> Tuple[float, List[str], List[str]]:
    best_score = 0.0
    positive_signals: List[str] = []
    negative_signals: List[str] = []

    for title in title_candidates:
        local_score = 0.0
        local_positive: List[str] = []
        local_negative: List[str] = []

        for pattern, points, reason in TITLE_POSITIVE_RULES:
            if re.search(pattern, title):
                local_score += points
                local_positive.append(f"{reason}: {title}")

        has_schedule_term = bool(re.search(r"\bSCHEDULE\b|\bWINDOW\b|\bGLAZING\b|\bOPENING\b|\bFENESTRATION\b", title))
        for pattern, points, reason in TITLE_NEGATIVE_RULES:
            if re.search(pattern, title):
                if "ELEVATION" in reason and has_schedule_term:
                    continue
                if title_source == "pdf_outline" and re.search(r"\bWINDOW\b", title) and re.search(r"\bSCHEDULE\b", title):
                    continue
                local_score += points
                local_negative.append(f"{reason}: {title}")

        if local_score > best_score:
            best_score = local_score
        positive_signals.extend(local_positive)
        negative_signals.extend(local_negative)

    if title_source == "pdf_outline" and best_score > 0:
        positive_signals.append("PDF outline/sidebar/bookmark title used as primary title source")
        best_score += 5

    best_score = max(0.0, min(100.0, best_score))
    return best_score, positive_signals, negative_signals


def count_known_headers(norm_text: str) -> Tuple[int, List[str]]:
    headers = {
        "TAG": r"\bTAG\b|\bMARK\b",
        "TYPE": r"\bTYPE\b",
        "QTY": r"\bQTY\b|\bQUANTITY\b",
        "WIDTH": r"\bWIDTH\b|\bWID\b",
        "HEIGHT": r"\bHEIGHT\b|\bHT\b",
        "U_VALUE": r"\bU[\-\s]?VALUE\b|\bU[\-\s]?FACTOR\b",
        "SHGC": r"\bSHGC\b",
        "VT": r"\bVT\b|\bVISIBLE TRANSMITTANCE\b",
        "GLASS": r"\bGLASS\b|\bGLAZING\b",
        "MATERIAL": r"\bMATERIAL\b|\bFRAME\b",
        "AREA": r"\bAREA\b",
    }
    found = []
    for name, pattern in headers.items():
        if re.search(pattern, norm_text):
            found.append(name)
    return len(found), found


def score_native_text(text: str) -> Tuple[float, List[str], List[str]]:
    norm_text = normalize_for_matching(text)
    score = 0.0
    positive_signals: List[str] = []
    negative_signals: List[str] = []

    for pattern, points, reason in NATIVE_POSITIVE_RULES:
        if re.search(pattern, norm_text):
            score += points
            positive_signals.append(reason)

    for pattern, points, reason in NATIVE_NEGATIVE_RULES:
        if re.search(pattern, norm_text):
            score += points
            negative_signals.append(reason)

    window_tags = re.findall(r"\bW[-\s]?\d{1,3}[A-Z]?\b", norm_text)
    unique_window_tags = sorted(set(window_tags))
    if len(unique_window_tags) >= 2:
        score += 15
        positive_signals.append(f"detected repeated window tag pattern: {', '.join(unique_window_tags[:8])}")

    header_count, found_headers = count_known_headers(norm_text)
    if header_count >= 4:
        score += 10
        positive_signals.append(f"detected {header_count} known schedule headers: {', '.join(found_headers)}")
    if header_count >= 6:
        score += 8
        positive_signals.append(f"detected very strong header coverage: {', '.join(found_headers)}")

    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    table_like_lines = 0
    for ln in lines:
        if len(ln) < 120 and re.search(r"\d", ln) and re.search(r"[A-Za-z]", ln):
            table_like_lines += 1
    if table_like_lines >= 8:
        score += 15
        positive_signals.append(f"detected table-like repeated rows: {table_like_lines} lines")

    if len(norm_text) < 80:
        score -= 20
        negative_signals.append("native text is very short; page may be scanned or text extraction failed")

    score = max(0.0, min(100.0, score))
    return score, positive_signals, negative_signals


# ── Analyzer class ────────────────────────────────────────────────────────────

class PDFPageAnalyzer:
    """Per-page deterministic analysis. Mirrors `analyze_pdf_pages` in the prototype."""

    def extract_outline_titles(self, doc: fitz.Document) -> Dict[int, List[str]]:
        return extract_outline_titles(doc)

    def analyze(
        self,
        doc: fitz.Document,
        outline_titles_by_page: Dict[int, List[str]],
    ) -> List[PageAnalysis]:
        log_section("1. PyMuPDF outline/sidebar + native text deterministic page analysis")
        analyses: List[PageAnalysis] = []

        if outline_titles_by_page:
            log_debug("Embedded PDF outline/sidebar/bookmark titles FOUND. They will be used before heuristic titles.")
            for idx, titles in sorted(outline_titles_by_page.items()):
                log_debug(f"Outline page {idx + 1}: {titles}")
        else:
            log_debug("No embedded PDF outline/sidebar/bookmark titles found. Falling back to heuristic title extraction.")

        for idx, page in enumerate(doc):
            page_number = idx + 1
            text = extract_native_text(page)

            title_candidates, title_source, outline_titles, heuristic_titles = choose_title_candidates(
                page_index=idx,
                outline_titles_by_page=outline_titles_by_page,
                page=page,
                native_text=text,
            )

            sheet_numbers = extract_sheet_numbers(text)

            title_score, title_pos, title_neg = score_title_candidates(title_candidates, title_source)
            native_score, native_pos, native_neg = score_native_text(text)

            final_score = title_score * 0.65 + native_score * 0.35

            analysis = PageAnalysis(
                page_index=idx,
                page_number=page_number,
                text=text,
                text_length=len(text),
                title_candidates=title_candidates,
                title_source=title_source,
                outline_titles=outline_titles,
                heuristic_titles=heuristic_titles,
                sheet_number_candidates=sheet_numbers,
                title_score=round(title_score, 2),
                native_text_score=round(native_score, 2),
                final_score=round(final_score, 2),
                positive_signals=title_pos + native_pos,
                negative_signals=title_neg + native_neg,
            )
            analyses.append(analysis)

            log_debug(
                f"Page {page_number}: title_source={analysis.title_source}, "
                f"title_score={analysis.title_score}, native_text_score={analysis.native_text_score}, "
                f"final_score={analysis.final_score}, text_len={analysis.text_length}"
            )
            if outline_titles:
                log_debug(f"  outline_titles={outline_titles}")
            if heuristic_titles:
                log_debug(f"  heuristic_titles={heuristic_titles[:5]}")
            if title_candidates:
                log_debug(f"  title_candidates_used={title_candidates[:5]}")
            if sheet_numbers:
                log_debug(f"  sheet_number_candidates={sheet_numbers[:5]}")
            if analysis.positive_signals:
                log_debug(f"  positive_signals={analysis.positive_signals[:6]}")
            if analysis.negative_signals:
                log_debug(f"  negative_signals={analysis.negative_signals[:6]}")
            log_debug(f"  native_text_preview={preview_text(text)}")

        return analyses
