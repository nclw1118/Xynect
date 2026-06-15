"""Internal dataclasses for the PDF extraction pipeline.

Ported verbatim from NOTEBOOKS/pdf_algo_test.py — semantics unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class PageAnalysis:
    page_index: int
    page_number: int
    text: str
    text_length: int
    title_candidates: List[str] = field(default_factory=list)
    title_source: str = "unknown"  # pdf_outline | heuristic_text_blocks | none
    outline_titles: List[str] = field(default_factory=list)
    heuristic_titles: List[str] = field(default_factory=list)
    sheet_number_candidates: List[str] = field(default_factory=list)
    title_score: float = 0.0
    native_text_score: float = 0.0
    final_score: float = 0.0
    selected: bool = False
    selection_reason: str = ""
    positive_signals: List[str] = field(default_factory=list)
    negative_signals: List[str] = field(default_factory=list)


@dataclass
class RenderedPage:
    page_index: int
    page_number: int
    png_path: str
    data_uri: str
    width_px: int
    height_px: int
    dpi: int


@dataclass
class CropRender:
    page_index: int
    page_number: int
    crop_index: int
    label: str
    method: str
    normalized_bbox_original: List[float]
    normalized_bbox_expanded: List[float]
    pdf_rect_points: List[float]
    png_path: str
    overlay_path: str
    data_uri: str
    width_px: int
    height_px: int
    dpi: int
    confidence: float
    reason: str


@dataclass
class CropPlanDebug:
    page_number: int
    contains_schedule: bool
    schedule_type: str
    readability: str
    can_extract_without_crop: bool
    needs_crop: bool
    crop_regions: List[Dict[str, Any]]
    confidence: float
    reason: str
    warnings: List[str]


@dataclass
class LLMPageResult:
    page_number: int
    contains_schedule: bool
    schedule_type: str
    confidence: float
    reason: str
    extracted_rows: List[Dict[str, Any]]  # window/opening/glazing rows
    extracted_door_rows: List[Dict[str, Any]] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    raw_response: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PDFExtractionArtifacts:
    """Full debug payload, serialized to extraction_result.json."""

    pdf_source: str
    file_type: str
    page_count: int
    outline_titles_by_page: Dict[str, List[str]]
    candidate_pages: List[Dict[str, Any]]
    rendered_pages: List[Dict[str, Any]]
    crop_plans: List[Dict[str, Any]]
    crop_renders: List[Dict[str, Any]]
    llm_results: List[Dict[str, Any]]
    extracted_window_rows: List[Dict[str, Any]]
    warnings: List[str]
    debug_trace: Dict[str, Any]
    extracted_door_rows: List[Dict[str, Any]] = field(default_factory=list)
    project_info: Dict[str, Any] = field(default_factory=dict)
