"""Deterministic elevation crop + overlay rendering (M2).

Renders one PNG per planned ElevationRegion and one numbered overlay per page.
Reuses PDFRenderer's bbox math (expand + normalized→pdf-rect) so we do not
duplicate that logic; only the area policy and filename/overlay scheme differ
from the schedule crop renderer (elevations can legitimately be large).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Tuple

import fitz  # PyMuPDF

from app.services.extraction.pdf._helpers import log_debug, log_section
from app.services.extraction.pdf.config import PDFExtractionConfig
from app.services.extraction.pdf.renderer import PDFRenderer
from app.services.extraction.pdf.schemas import ElevationPageCandidate, ElevationRegion

# Elevations can fill most of a sheet, so the upper bound is looser than the
# schedule crop policy (config.max_crop_area_ratio).
ELEV_MIN_AREA = 0.01
ELEV_MAX_AREA = 0.98


def validate_clamp_bbox(bbox) -> Tuple[bool, List[float], str]:
    """Clamp a normalized bbox to [0,1] and validate its area.

    Returns (ok, clamped_bbox, reason). ok is False for degenerate or
    out-of-area boxes; clamped_bbox is always a sane 4-tuple.
    """
    if not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
        return False, [0.0, 0.0, 1.0, 1.0], "bbox must be a list of four numbers"
    try:
        x0, y0, x1, y1 = [float(v) for v in bbox]
    except Exception:
        return False, [0.0, 0.0, 1.0, 1.0], "bbox values must be numeric"

    x0 = max(0.0, min(1.0, x0))
    y0 = max(0.0, min(1.0, y0))
    x1 = max(0.0, min(1.0, x1))
    y1 = max(0.0, min(1.0, y1))
    if x1 < x0:
        x0, x1 = x1, x0
    if y1 < y0:
        y0, y1 = y1, y0

    clamped = [x0, y0, x1, y1]
    area = (x1 - x0) * (y1 - y0)
    if (x1 - x0) <= 0 or (y1 - y0) <= 0:
        return False, clamped, "bbox has zero width or height"
    if area < ELEV_MIN_AREA:
        return False, clamped, f"bbox too small: area ratio={area:.4f}"
    if area > ELEV_MAX_AREA:
        return False, clamped, f"bbox too large: area ratio={area:.4f}"
    return True, clamped, ""


def _safe_direction(direction: str, used: Dict[str, int]) -> str:
    base = re.sub(r"[^a-z0-9]+", "_", (direction or "unknown").lower()).strip("_") or "unknown"
    used[base] = used.get(base, 0) + 1
    return base if used[base] == 1 else f"{base}_{used[base]}"


class PDFElevationCropRenderer:
    def __init__(self, config: PDFExtractionConfig, renderer: PDFRenderer):
        self.config = config
        self.renderer = renderer

    def render_page_regions(
        self,
        doc: fitz.Document,
        candidate: ElevationPageCandidate,
        regions: List[ElevationRegion],
        out_dir: Path,
    ) -> Tuple[List[Dict], str]:
        """Render crops + a numbered overlay for one elevation page.

        Returns (region_debug_dicts, overlay_path). overlay_path is "" if no
        valid region was rendered.
        """
        log_section(f"E3. Elevation crop rendering (page {candidate.page_number})")

        page = doc[candidate.page_index]
        page_no = candidate.page_number
        used_names: Dict[str, int] = {}
        region_dicts: List[Dict] = []
        valid_rects: List[Tuple[fitz.Rect, str]] = []  # (rect, label) for overlay

        for region in regions:
            ok, clamped, reason = validate_clamp_bbox(region.bbox)
            entry: Dict = {
                "page_number": page_no,
                "page_index": candidate.page_index,
                "sheet_number": region.sheet_number or candidate.sheet_number,
                "direction": region.direction,
                "scale": region.scale or candidate.scale,
                "bbox_original": clamped,
                "confidence": region.confidence,
                "reason": region.reason,
                "png_path": None,
                "valid": ok,
            }
            if not ok:
                entry["skip_reason"] = reason
                log_debug(f"  rejected {region.direction} crop on page {page_no}: {reason}")
                region_dicts.append(entry)
                continue

            expanded = self.renderer.expand_normalized_bbox(clamped)
            crop_rect = self.renderer.normalized_bbox_to_pdf_rect(page, expanded)

            zoom = self.config.crop_dpi / 72.0
            pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), clip=crop_rect, alpha=False)

            name = _safe_direction(region.direction, used_names)
            png_path = out_dir / f"elevation_page_{page_no:03d}_{name}.png"
            png_path.write_bytes(pix.tobytes("png"))

            entry["bbox_expanded"] = expanded
            entry["png_path"] = str(png_path)
            entry["width_px"] = pix.width
            entry["height_px"] = pix.height
            entry["dpi"] = self.config.crop_dpi
            region_dicts.append(entry)
            valid_rects.append((crop_rect, name))
            log_debug(
                f"  rendered {name} crop on page {page_no}: {pix.width}x{pix.height}px, "
                f"bbox={expanded}, path={png_path}"
            )

        overlay_path = self._render_overlay(doc, candidate, valid_rects, out_dir) if valid_rects else ""
        return region_dicts, overlay_path

    def _render_overlay(
        self,
        doc: fitz.Document,
        candidate: ElevationPageCandidate,
        rects: List[Tuple["fitz.Rect", str]],
        out_dir: Path,
    ) -> str:
        page_no = candidate.page_number
        overlay_path = out_dir / f"elevation_page_{page_no:03d}_overlay.png"
        try:
            tmp_doc = fitz.open()
            tmp_doc.insert_pdf(doc, from_page=candidate.page_index, to_page=candidate.page_index)
            tmp_page = tmp_doc[0]
            for idx, (rect, name) in enumerate(rects, start=1):
                tmp_page.draw_rect(rect, color=(1, 0, 0), width=3)
                try:
                    tmp_page.insert_text(
                        fitz.Point(rect.x0 + 4, max(rect.y0 + 14, 14)),
                        f"{idx}. {name}",
                        color=(1, 0, 0),
                        fontsize=12,
                    )
                except Exception:
                    pass
            zoom = self.config.overlay_dpi / 72.0
            pix = tmp_page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
            overlay_path.write_bytes(pix.tobytes("png"))
            tmp_doc.close()
            log_debug(f"  elevation overlay page {page_no}: {overlay_path}")
            return str(overlay_path)
        except Exception as exc:
            log_debug(f"  could not render elevation overlay for page {page_no}: {exc}")
            return ""
