"""High-DPI full-page + crop rendering with PyMuPDF.

Bbox math and rendering logic ported verbatim from NOTEBOOKS/pdf_algo_test.py.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import List, Tuple

import fitz  # PyMuPDF

from app.services.extraction.pdf._helpers import (
    log_debug,
    log_section,
    png_bytes_to_data_uri,
)
from app.services.extraction.pdf.config import PDFExtractionConfig
from app.services.extraction.pdf.models import CropRender, PageAnalysis, RenderedPage
from app.services.extraction.pdf.schemas import CropRegionPlan


class PDFRenderer:
    def __init__(self, config: PDFExtractionConfig):
        self.config = config

    # ── Bbox math ─────────────────────────────────────────────────────────────

    def validate_normalized_bbox(self, bbox: List[float]) -> Tuple[bool, List[float], str]:
        if not isinstance(bbox, list) or len(bbox) != 4:
            return False, [0, 0, 1, 1], "bbox must be a list of four numbers"

        try:
            x0, y0, x1, y1 = [float(v) for v in bbox]
        except Exception:
            return False, [0, 0, 1, 1], "bbox values must be numeric"

        x0 = max(0.0, min(1.0, x0))
        y0 = max(0.0, min(1.0, y0))
        x1 = max(0.0, min(1.0, x1))
        y1 = max(0.0, min(1.0, y1))

        if x1 < x0:
            x0, x1 = x1, x0
        if y1 < y0:
            y0, y1 = y1, y0

        width = x1 - x0
        height = y1 - y0
        area = width * height

        if width <= 0 or height <= 0:
            return False, [x0, y0, x1, y1], "bbox has zero width or height"
        if area < self.config.min_crop_area_ratio:
            return False, [x0, y0, x1, y1], f"bbox too small: area ratio={area:.4f}"
        if area > self.config.max_crop_area_ratio:
            return False, [x0, y0, x1, y1], f"bbox too large: area ratio={area:.4f}"

        return True, [x0, y0, x1, y1], ""

    def expand_normalized_bbox(self, bbox: List[float]) -> List[float]:
        x0, y0, x1, y1 = bbox
        width = x1 - x0
        height = y1 - y0

        dx = width * self.config.crop_expand_ratio
        dy = height * self.config.crop_expand_ratio

        return [
            max(0.0, x0 - dx),
            max(0.0, y0 - dy),
            min(1.0, x1 + dx),
            min(1.0, y1 + dy),
        ]

    @staticmethod
    def normalized_bbox_to_pdf_rect(page: fitz.Page, bbox: List[float]) -> fitz.Rect:
        page_rect = page.rect
        x0, y0, x1, y1 = bbox
        return fitz.Rect(
            page_rect.x0 + x0 * page_rect.width,
            page_rect.y0 + y0 * page_rect.height,
            page_rect.x0 + x1 * page_rect.width,
            page_rect.y0 + y1 * page_rect.height,
        )

    # ── Full-page render ──────────────────────────────────────────────────────

    def render_full_page(
        self,
        doc: fitz.Document,
        page_analysis: PageAnalysis,
        out_dir: Path,
    ) -> RenderedPage:
        dpi = self.config.render_dpi
        page = doc[page_analysis.page_index]
        zoom = dpi / 72.0
        matrix = fitz.Matrix(zoom, zoom)

        pix = page.get_pixmap(matrix=matrix, alpha=False)
        png_bytes = pix.tobytes("png")

        png_filename = f"page_{page_analysis.page_number:03d}_{dpi}dpi_full.png"
        png_path = out_dir / png_filename
        png_path.write_bytes(png_bytes)

        return RenderedPage(
            page_index=page_analysis.page_index,
            page_number=page_analysis.page_number,
            png_path=str(png_path),
            data_uri=png_bytes_to_data_uri(png_bytes),
            width_px=pix.width,
            height_px=pix.height,
            dpi=dpi,
        )

    def render_selected_pages(
        self,
        doc: fitz.Document,
        selected_pages: List[PageAnalysis],
        out_dir: Path,
    ) -> List[RenderedPage]:
        log_section("3. High-fidelity full-page rendering")
        rendered: List[RenderedPage] = []

        for page_analysis in selected_pages:
            rp = self.render_full_page(doc, page_analysis, out_dir)
            rendered.append(rp)
            log_debug(
                f"Rendered page {rp.page_number}: {rp.width_px}x{rp.height_px}px, "
                f"dpi={rp.dpi}, path={rp.png_path}"
            )

        return rendered

    # ── Crop render ───────────────────────────────────────────────────────────

    def render_crop(
        self,
        doc: fitz.Document,
        page_analysis: PageAnalysis,
        crop_plan: CropRegionPlan,
        crop_index: int,
        out_dir: Path,
    ) -> CropRender | None:
        ok, bbox, reason = self.validate_normalized_bbox(crop_plan.normalized_bbox)
        if not ok:
            log_debug(f"Rejected crop page {page_analysis.page_number} crop {crop_index}: {reason}")
            return None

        expanded_bbox = self.expand_normalized_bbox(bbox)
        page = doc[page_analysis.page_index]
        crop_rect = self.normalized_bbox_to_pdf_rect(page, expanded_bbox)

        zoom = self.config.crop_dpi / 72.0
        matrix = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=matrix, clip=crop_rect, alpha=False)
        png_bytes = pix.tobytes("png")

        safe_label = re.sub(r"[^A-Za-z0-9_\-]+", "_", crop_plan.label.strip())[:50] or "crop"
        crop_filename = (
            f"page_{page_analysis.page_number:03d}_crop_{crop_index:02d}_"
            f"{safe_label}_{self.config.crop_dpi}dpi.png"
        )
        crop_path = out_dir / crop_filename
        crop_path.write_bytes(png_bytes)

        # Overlay image for debugging
        overlay_path = out_dir / f"page_{page_analysis.page_number:03d}_crop_{crop_index:02d}_overlay.png"
        try:
            tmp_doc = fitz.open()
            tmp_doc.insert_pdf(doc, from_page=page_analysis.page_index, to_page=page_analysis.page_index)
            tmp_page = tmp_doc[0]
            tmp_page.draw_rect(crop_rect, color=(1, 0, 0), width=3)
            overlay_zoom = self.config.overlay_dpi / 72.0
            overlay_pix = tmp_page.get_pixmap(matrix=fitz.Matrix(overlay_zoom, overlay_zoom), alpha=False)
            overlay_path.write_bytes(overlay_pix.tobytes("png"))
            tmp_doc.close()
        except Exception as exc:
            log_debug(f"Could not create crop overlay for page {page_analysis.page_number}: {exc}")
            overlay_path = Path("")

        crop_render = CropRender(
            page_index=page_analysis.page_index,
            page_number=page_analysis.page_number,
            crop_index=crop_index,
            label=crop_plan.label,
            method="llm_normalized_bbox",
            normalized_bbox_original=bbox,
            normalized_bbox_expanded=expanded_bbox,
            pdf_rect_points=[crop_rect.x0, crop_rect.y0, crop_rect.x1, crop_rect.y1],
            png_path=str(crop_path),
            overlay_path=str(overlay_path) if str(overlay_path) else "",
            data_uri=png_bytes_to_data_uri(png_bytes),
            width_px=pix.width,
            height_px=pix.height,
            dpi=self.config.crop_dpi,
            confidence=float(crop_plan.confidence or 0.0),
            reason=crop_plan.reason,
        )

        log_debug(
            f"Rendered crop page {page_analysis.page_number} crop {crop_index}: "
            f"{pix.width}x{pix.height}px, bbox={expanded_bbox}, path={crop_path}"
        )
        if crop_render.overlay_path:
            log_debug(f"  Overlay debug image: {crop_render.overlay_path}")

        return crop_render
