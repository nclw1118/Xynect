"""Fast deterministic page routing — a cheap pre-pass before the heavy analyzer.

For many architectural PDFs the embedded outline / native sheet title already
identifies the pages we care about, e.g.:

    A-401.00 - WINDOW, DOOR, WALL & FLOOR SCHEDULE   -> combined schedule
    A-201.00 - WEST/EAST_ELEVATION                   -> elevation
    A-202.00 - NORTH/SOUTH_ELEVATION                 -> elevation

This module routes such pages using ONLY cheap deterministic signals:

* PDF outline / bookmark titles
* native page title / title-block text (no font analysis)
* drawing list / sheet index references
* page-text keyword matching
* sheet-number patterns like A-201.00 / A-401.00

It NEVER renders a page and NEVER calls an LLM. When it is confident
(`confidence == "high"` and at least one schedule page found) the caller can
skip the expensive page_analyzer + candidate_selector path. Otherwise the
caller falls back to the existing robust logic unchanged.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Dict, List, Literal, Optional, Tuple

import fitz  # PyMuPDF

from app.services.extraction.pdf._helpers import (
    log_debug,
    log_section,
    normalize_for_matching,
)
from app.services.extraction.pdf.page_analyzer import (
    extract_outline_titles,
    extract_sheet_numbers,
)


# ── Deterministic keyword sets (matched against normalized text) ───────────────
# normalize_for_matching uppercases, turns "&" into " AND ", drops other
# punctuation, and collapses whitespace. So:
#   "WINDOW, DOOR, WALL & FLOOR SCHEDULE" -> "WINDOW DOOR WALL AND FLOOR SCHEDULE"
#   "WINDOW/DOOR SCHEDULE"                -> "WINDOW DOOR SCHEDULE"
# All triggers below are written in that normalized form.

# Canonical schedule phrases (for matched_terms reporting). Detection itself
# uses SCHEDULE_RE below, which generalizes these to tolerate plurals
# ("WINDOWS & DOORS SCHEDULE") and combined titles with intervening words
# ("WINDOW, DOOR, WALL & FLOOR SCHEDULE").
SCHEDULE_TRIGGERS: List[str] = [
    "WINDOW SCHEDULE",
    "WINDOWS SCHEDULE",
    "DOOR SCHEDULE",
    "DOORS SCHEDULE",
    "EXTERIOR DOOR SCHEDULE",
    "INTERIOR DOOR SCHEDULE",
    "WINDOW DOOR WALL AND FLOOR SCHEDULE",
    "WINDOW AND DOOR SCHEDULE",
    "WINDOWS AND DOORS SCHEDULE",
    "WINDOW DOOR SCHEDULE",
    "FENESTRATION SCHEDULE",
]

# A title/line is a window/door schedule reference if an opening keyword
# (WINDOW(S) / DOOR(S) / FENESTRATION / GLAZING / OPENING(S)) is followed by
# SCHEDULE on the same line, possibly with intervening words (WALL, FLOOR, &).
# Operates on normalized text (uppercase, "&"->"AND", punctuation->space), so
# it matches "WINDOWS AND DOORS SCHEDULE", "WINDOW DOOR WALL AND FLOOR
# SCHEDULE", "EXTERIOR DOOR SCHEDULE", etc.
SCHEDULE_RE = re.compile(
    r"\b(?:WINDOWS?|DOORS?|FENESTRATION|GLAZING|OPENINGS?)\b[A-Z0-9\s\.\-]*\bSCHEDULE\b"
)

ELEVATION_TRIGGER = "ELEVATION"
ELEVATION_DIRECTIONAL: List[str] = [
    "EAST ELEVATION",
    "WEST ELEVATION",
    "NORTH ELEVATION",
    "SOUTH ELEVATION",
    "FRONT ELEVATION",
    "REAR ELEVATION",
    "LEFT ELEVATION",
    "RIGHT ELEVATION",
]

PROJECT_INFO_TRIGGERS: List[str] = [
    "COVER SHEET",
    "TITLE SHEET",
    "GENERAL NOTES",
    "PROJECT INFORMATION",
    "ZONING ANALYSIS",
]

# Pages that are themselves a drawing index list many sheet titles; we must not
# treat their entries as page-local titles.
DRAWING_LIST_TRIGGERS: List[str] = [
    "DRAWING LIST",
    "DRAWING INDEX",
    "SHEET INDEX",
    "SHEET LIST",
    "INDEX OF DRAWINGS",
    "DRAWING SCHEDULE",
]

SHEET_NUMBER_RE = re.compile(r"\b[A-Z]{1,3}[-\s]?\d{1,3}(?:\.\d+)?\b")

# Confidence levels per source (see requirement 6).
CONF_EXACT_TITLE = 0.95   # exact phrase from outline / native page title
CONF_DRAWING_LIST = 0.75  # referenced by a drawing list, page-local title missing
CONF_TEXT_KEYWORD = 0.70  # broad native-text keyword only
CONF_FIRST_PAGE = 0.50    # page 1 always kept as a project-info candidate

# Strong sources are page-local titles; only these can push overall confidence
# to "high".
STRONG_SOURCES = ("pdf_outline", "native_title")

# Max chars of slack a line may have beyond a phrase to still be "title-like".
# Allows a leading sheet number, e.g. "A-401.00 - WINDOW SCHEDULE".
TITLE_SLACK = 30


@dataclass
class RoutedPage:
    page_index: int
    page_number: int
    role: str  # window_schedule | door_schedule | combined_schedule | elevation | project_info
    sheet_number: Optional[str]
    sheet_title: Optional[str]
    confidence: float
    source: str  # pdf_outline | native_title | drawing_list | text_keyword | first_page_default
    matched_terms: List[str] = field(default_factory=list)


@dataclass
class FastPageRoutingResult:
    schedule_candidates: List[RoutedPage]
    elevation_candidates: List[RoutedPage]
    project_info_candidates: List[RoutedPage]
    confidence: Literal["high", "medium", "low"]
    used_fast_path: bool
    warnings: List[str] = field(default_factory=list)
    debug: dict = field(default_factory=dict)

    def to_debug_dict(self) -> dict:
        return {
            "confidence": self.confidence,
            "used_fast_path": self.used_fast_path,
            "schedule_candidates": [asdict(c) for c in self.schedule_candidates],
            "elevation_candidates": [asdict(c) for c in self.elevation_candidates],
            "project_info_candidates": [asdict(c) for c in self.project_info_candidates],
            "warnings": list(self.warnings),
            "debug": self.debug,
        }


# ── Small helpers ──────────────────────────────────────────────────────────────

def _is_title_like(norm_line: str, phrase: str) -> bool:
    """A line is title-like for a phrase if the phrase dominates the line."""
    if phrase not in norm_line:
        return False
    return len(norm_line) <= len(phrase) + TITLE_SLACK


def _pick_sheet(sheet_numbers: List[str], from_text: Optional[str] = None) -> Optional[str]:
    """Prefer a sheet number embedded in the matched title; else first on page."""
    if from_text:
        m = SHEET_NUMBER_RE.search(from_text)
        if m:
            return m.group(0).strip()
    return sheet_numbers[0] if sheet_numbers else None


def _schedule_role(title_text: str) -> str:
    has_window = ("WINDOW" in title_text) or ("FENESTRATION" in title_text)
    has_door = "DOOR" in title_text
    if has_window and has_door:
        return "combined_schedule"
    if has_door and not has_window:
        return "door_schedule"
    return "window_schedule"


def _schedule_terms(norm: str, match: "re.Match") -> List[str]:
    """matched_terms: canonical phrases present, else the raw matched phrase."""
    hits = [t for t in SCHEDULE_TRIGGERS if t in norm]
    return hits or [match.group(0).strip()]


@dataclass
class _PageData:
    page_index: int
    page_number: int
    norm_full: str
    raw_lines: List[str]
    norm_lines: List[str]
    outline_raw: List[str]
    outline_norm: List[str]
    sheet_numbers: List[str]
    is_drawing_list: bool


# ── Per-page direct detection ──────────────────────────────────────────────────

def _detect_schedule(pd: _PageData) -> Optional[RoutedPage]:
    # 1) PDF outline title for this page (strong, independent of page text).
    for raw, norm in zip(pd.outline_raw, pd.outline_norm):
        m = SCHEDULE_RE.search(norm)
        if m:
            return RoutedPage(
                page_index=pd.page_index,
                page_number=pd.page_number,
                role=_schedule_role(norm),
                sheet_number=_pick_sheet(pd.sheet_numbers, norm),
                sheet_title=raw,
                confidence=CONF_EXACT_TITLE,
                source="pdf_outline",
                matched_terms=_schedule_terms(norm, m),
            )

    # 2) Native page-local title line (a short line dominated by the phrase).
    for raw, norm in zip(pd.raw_lines, pd.norm_lines):
        m = SCHEDULE_RE.search(norm)
        if m and len(norm) <= len(m.group(0)) + TITLE_SLACK:
            return RoutedPage(
                page_index=pd.page_index,
                page_number=pd.page_number,
                role=_schedule_role(norm),
                sheet_number=_pick_sheet(pd.sheet_numbers, norm),
                sheet_title=raw.strip(),
                confidence=CONF_EXACT_TITLE,
                source="native_title",
                matched_terms=_schedule_terms(norm, m),
            )

    # 3) Broad native-text keyword: any line mentioning a schedule phrase.
    for raw, norm in zip(pd.raw_lines, pd.norm_lines):
        m = SCHEDULE_RE.search(norm)
        if m:
            return RoutedPage(
                page_index=pd.page_index,
                page_number=pd.page_number,
                role=_schedule_role(norm),
                sheet_number=_pick_sheet(pd.sheet_numbers),
                sheet_title=None,
                confidence=CONF_TEXT_KEYWORD,
                source="text_keyword",
                matched_terms=_schedule_terms(norm, m),
            )

    return None


def _detect_elevation(pd: _PageData) -> Optional[RoutedPage]:
    text_has = ELEVATION_TRIGGER in pd.norm_full
    outline_has = any(ELEVATION_TRIGGER in norm for norm in pd.outline_norm)
    if not text_has and not outline_has:
        return None

    # 1) PDF outline title (strong, independent of page text).
    for raw, norm in zip(pd.outline_raw, pd.outline_norm):
        if ELEVATION_TRIGGER in norm:
            terms = [ELEVATION_TRIGGER] + [d for d in ELEVATION_DIRECTIONAL if d in norm]
            return RoutedPage(
                page_index=pd.page_index,
                page_number=pd.page_number,
                role="elevation",
                sheet_number=_pick_sheet(pd.sheet_numbers, norm),
                sheet_title=raw,
                confidence=CONF_EXACT_TITLE,
                source="pdf_outline",
                matched_terms=terms,
            )

    # 2) Native page-local title line.
    for raw, norm in zip(pd.raw_lines, pd.norm_lines):
        if _is_title_like(norm, ELEVATION_TRIGGER):
            terms = [ELEVATION_TRIGGER] + [d for d in ELEVATION_DIRECTIONAL if d in norm]
            return RoutedPage(
                page_index=pd.page_index,
                page_number=pd.page_number,
                role="elevation",
                sheet_number=_pick_sheet(pd.sheet_numbers, norm),
                sheet_title=raw.strip(),
                confidence=CONF_EXACT_TITLE,
                source="native_title",
                matched_terms=terms,
            )

    # 3) Broad native-text keyword only.
    terms = [ELEVATION_TRIGGER] + [d for d in ELEVATION_DIRECTIONAL if d in pd.norm_full]
    return RoutedPage(
        page_index=pd.page_index,
        page_number=pd.page_number,
        role="elevation",
        sheet_number=_pick_sheet(pd.sheet_numbers),
        sheet_title=None,
        confidence=CONF_TEXT_KEYWORD,
        source="text_keyword",
        matched_terms=terms,
    )


def _detect_project_info(pd: _PageData) -> Optional[RoutedPage]:
    matched = [t for t in PROJECT_INFO_TRIGGERS if t in pd.norm_full]
    if not matched:
        return None

    # Prefer a page-local title line for the matched term.
    for raw, norm in zip(pd.raw_lines, pd.norm_lines):
        hits = [t for t in matched if _is_title_like(norm, t)]
        if hits:
            return RoutedPage(
                page_index=pd.page_index,
                page_number=pd.page_number,
                role="project_info",
                sheet_number=_pick_sheet(pd.sheet_numbers, norm),
                sheet_title=raw.strip(),
                confidence=CONF_EXACT_TITLE,
                source="native_title",
                matched_terms=hits,
            )

    return RoutedPage(
        page_index=pd.page_index,
        page_number=pd.page_number,
        role="project_info",
        sheet_number=_pick_sheet(pd.sheet_numbers),
        sheet_title=None,
        confidence=CONF_TEXT_KEYWORD,
        source="text_keyword",
        matched_terms=matched,
    )


# ── Drawing-list resolution (cross-page) ───────────────────────────────────────

def _resolve_drawing_list(
    pages: List[_PageData],
    direct_schedule_idx: set,
    direct_elevation_idx: set,
) -> Tuple[List[RoutedPage], List[RoutedPage], List[str]]:
    """Resolve schedule/elevation references found in drawing-list pages.

    Used only for pages that lack their own page-local title. Such candidates
    carry CONF_DRAWING_LIST and require downstream validation.
    """
    schedule: List[RoutedPage] = []
    elevation: List[RoutedPage] = []
    warnings: List[str] = []

    drawing_list_pages = [pd for pd in pages if pd.is_drawing_list]
    if not drawing_list_pages:
        return schedule, elevation, warnings

    def _find_target(sheet_no: str, exclude_idx: int) -> Optional[_PageData]:
        token_re = re.compile(r"(?<![A-Z0-9])" + re.escape(sheet_no) + r"(?![0-9])")
        for pd in pages:
            if pd.page_index == exclude_idx:
                continue
            if token_re.search(pd.norm_full):
                return pd
        return None

    for dl in drawing_list_pages:
        for raw, norm in zip(dl.raw_lines, dl.norm_lines):
            m = SHEET_NUMBER_RE.search(norm)
            if not m:
                continue
            sheet_no = m.group(0).strip()

            sched_match = SCHEDULE_RE.search(norm)
            sched_hits = _schedule_terms(norm, sched_match) if sched_match else []
            elev = ELEVATION_TRIGGER in norm

            if not sched_hits and not elev:
                continue

            target = _find_target(sheet_no, dl.page_index)
            if not target:
                continue

            if sched_hits and target.page_index not in direct_schedule_idx:
                schedule.append(
                    RoutedPage(
                        page_index=target.page_index,
                        page_number=target.page_number,
                        role=_schedule_role(norm),
                        sheet_number=sheet_no,
                        sheet_title=raw.strip(),
                        confidence=CONF_DRAWING_LIST,
                        source="drawing_list",
                        matched_terms=sched_hits,
                    )
                )
                direct_schedule_idx.add(target.page_index)
                warnings.append(
                    f"Schedule page {target.page_number} routed from drawing list "
                    f"({sheet_no}); page-local title missing — requires validation."
                )

            if elev and target.page_index not in direct_elevation_idx:
                terms = [ELEVATION_TRIGGER] + [d for d in ELEVATION_DIRECTIONAL if d in norm]
                elevation.append(
                    RoutedPage(
                        page_index=target.page_index,
                        page_number=target.page_number,
                        role="elevation",
                        sheet_number=sheet_no,
                        sheet_title=raw.strip(),
                        confidence=CONF_DRAWING_LIST,
                        source="drawing_list",
                        matched_terms=terms,
                    )
                )
                direct_elevation_idx.add(target.page_index)

    return schedule, elevation, warnings


def _dedupe_best(candidates: List[RoutedPage]) -> List[RoutedPage]:
    """Keep the highest-confidence candidate per page, ordered by page number."""
    best: Dict[int, RoutedPage] = {}
    for c in candidates:
        existing = best.get(c.page_index)
        if existing is None or c.confidence > existing.confidence:
            best[c.page_index] = c
    return sorted(best.values(), key=lambda c: c.page_number)


# ── Router ─────────────────────────────────────────────────────────────────────

class FastPageRouter:
    """Cheap native-text / outline based routing pass."""

    def route(
        self,
        doc: fitz.Document,
        outline_titles_by_page: Optional[Dict[int, List[str]]] = None,
    ) -> FastPageRoutingResult:
        log_section("0. Fast deterministic page routing (pre-analyzer)")

        if outline_titles_by_page is None:
            outline_titles_by_page = extract_outline_titles(doc)

        pages: List[_PageData] = []
        for idx in range(doc.page_count):
            page = doc[idx]
            text = page.get_text("text", sort=True) or ""
            raw_lines = [ln for ln in text.splitlines() if ln.strip()]
            norm_lines = [normalize_for_matching(ln) for ln in raw_lines]
            norm_full = normalize_for_matching(text)
            outline_raw = list(outline_titles_by_page.get(idx, []))
            outline_norm = [normalize_for_matching(t) for t in outline_raw]
            is_drawing_list = any(t in norm_full for t in DRAWING_LIST_TRIGGERS)
            pages.append(
                _PageData(
                    page_index=idx,
                    page_number=idx + 1,
                    norm_full=norm_full,
                    raw_lines=raw_lines,
                    norm_lines=norm_lines,
                    outline_raw=outline_raw,
                    outline_norm=outline_norm,
                    sheet_numbers=extract_sheet_numbers(text),
                    is_drawing_list=is_drawing_list,
                )
            )

        schedule: List[RoutedPage] = []
        elevation: List[RoutedPage] = []
        project_info: List[RoutedPage] = []
        per_page_debug: List[dict] = []

        for pd in pages:
            sched = None if pd.is_drawing_list else _detect_schedule(pd)
            elev = None if pd.is_drawing_list else _detect_elevation(pd)
            pinfo = _detect_project_info(pd)

            if sched:
                schedule.append(sched)
            if elev:
                elevation.append(elev)
            if pinfo:
                project_info.append(pinfo)

            per_page_debug.append({
                "page_number": pd.page_number,
                "is_drawing_list": pd.is_drawing_list,
                "sheet_numbers": pd.sheet_numbers[:5],
                "schedule": asdict(sched) if sched else None,
                "elevation": asdict(elev) if elev else None,
                "project_info": asdict(pinfo) if pinfo else None,
            })

        # Cross-page drawing-list resolution for pages with no local title.
        direct_sched_idx = {c.page_index for c in schedule}
        direct_elev_idx = {c.page_index for c in elevation}
        dl_sched, dl_elev, dl_warnings = _resolve_drawing_list(
            pages, direct_sched_idx, direct_elev_idx
        )
        schedule.extend(dl_sched)
        elevation.extend(dl_elev)

        schedule = _dedupe_best(schedule)
        elevation = _dedupe_best(elevation)

        # ── Project-info: always page 1, then up to 2 keyword matches ──────────
        project_info_candidates: List[RoutedPage] = []
        seen_pi: set = set()
        if pages:
            first = pages[0]
            project_info_candidates.append(
                RoutedPage(
                    page_index=first.page_index,
                    page_number=first.page_number,
                    role="project_info",
                    sheet_number=_pick_sheet(first.sheet_numbers),
                    sheet_title=None,
                    confidence=CONF_FIRST_PAGE,
                    source="first_page_default",
                    matched_terms=[],
                )
            )
            seen_pi.add(first.page_index)
        for c in _dedupe_best(project_info):
            if c.page_index in seen_pi:
                continue
            project_info_candidates.append(c)
            seen_pi.add(c.page_index)
            if len(project_info_candidates) >= 3:  # page 1 + up to 2 matches
                break

        # ── Confidence ─────────────────────────────────────────────────────────
        strong_schedule = any(c.source in STRONG_SOURCES for c in schedule)
        strong_elevation = any(c.source in STRONG_SOURCES for c in elevation)

        if strong_schedule or strong_elevation:
            confidence: Literal["high", "medium", "low"] = "high"
        elif schedule or elevation:
            confidence = "medium"
        else:
            confidence = "low"

        # The fast path is only actionable for schedule extraction when we have
        # at least one schedule candidate. Elevation-only "high" still falls back
        # so window-schedule discovery is never skipped.
        used_fast_path = confidence == "high" and bool(schedule)

        warnings = list(dl_warnings)
        if confidence == "medium":
            warnings.append(
                "Fast router found only weak (drawing-list / broad-text) candidates; "
                "they require validation, falling back to heavy analyzer."
            )
        elif confidence == "low":
            warnings.append(
                "Fast router found no schedule/elevation candidates; falling back to heavy analyzer."
            )
        elif not used_fast_path:
            warnings.append(
                "Fast router is confident about elevations but found no schedule page; "
                "falling back to heavy analyzer for schedule discovery."
            )

        result = FastPageRoutingResult(
            schedule_candidates=schedule,
            elevation_candidates=elevation,
            project_info_candidates=project_info_candidates,
            confidence=confidence,
            used_fast_path=used_fast_path,
            warnings=warnings,
            debug={
                "page_count": doc.page_count,
                "outline_available": bool(outline_titles_by_page),
                "strong_schedule": strong_schedule,
                "strong_elevation": strong_elevation,
                "drawing_list_pages": [pd.page_number for pd in pages if pd.is_drawing_list],
                "per_page": per_page_debug,
            },
        )

        log_debug(
            f"Fast routing confidence={confidence}, used_fast_path={used_fast_path}, "
            f"schedule={[c.page_number for c in schedule]}, "
            f"elevation={[c.page_number for c in elevation]}, "
            f"project_info={[c.page_number for c in project_info_candidates]}"
        )
        for c in schedule:
            log_debug(
                f"  schedule p{c.page_number}: role={c.role}, source={c.source}, "
                f"conf={c.confidence}, terms={c.matched_terms}"
            )
        for c in elevation:
            log_debug(
                f"  elevation p{c.page_number}: source={c.source}, conf={c.confidence}, "
                f"terms={c.matched_terms}"
            )

        return result
