"""Config for the PDF extraction algorithm. Values come from app settings."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PDFExtractionConfig:
    # Rendering DPIs
    render_dpi: int
    crop_dpi: int
    overlay_dpi: int

    # Crop tuning
    crop_expand_ratio: float
    max_crop_regions_per_page: int
    min_crop_area_ratio: float
    max_crop_area_ratio: float

    # Candidate page selection
    strong_title_threshold: float
    top_native_text_backup_pages: int
    max_candidate_pages_sent_to_llm: int

    # Debug
    debug_output_dir: str
    save_debug_artifacts: bool

    # LLM
    openai_api_key: str
    llm_model: str

    @classmethod
    def from_settings(cls) -> "PDFExtractionConfig":
        from app.core.config import settings

        return cls(
            render_dpi=settings.pdf_render_dpi,
            crop_dpi=settings.pdf_crop_dpi,
            overlay_dpi=settings.pdf_overlay_dpi,
            crop_expand_ratio=settings.pdf_crop_expand_ratio,
            max_crop_regions_per_page=settings.pdf_max_crop_regions_per_page,
            min_crop_area_ratio=settings.pdf_min_crop_area_ratio,
            max_crop_area_ratio=settings.pdf_max_crop_area_ratio,
            strong_title_threshold=settings.pdf_strong_title_threshold,
            top_native_text_backup_pages=settings.pdf_top_native_text_backup_pages,
            max_candidate_pages_sent_to_llm=settings.pdf_max_candidate_pages_sent_to_llm,
            debug_output_dir=settings.pdf_debug_output_dir,
            save_debug_artifacts=settings.pdf_save_debug_artifacts,
            openai_api_key=settings.openai_api_key,
            llm_model=settings.llm_model,
        )
