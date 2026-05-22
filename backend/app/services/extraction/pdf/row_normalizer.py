"""Row normalization + deduplication.

Ported verbatim from `normalize_row` + `merge_and_normalize_rows` in
NOTEBOOKS/pdf_algo_test.py.
"""

from __future__ import annotations

from typing import Any, Dict, List

from app.services.extraction.pdf._helpers import clean_string, log_debug, log_section
from app.services.extraction.pdf.models import LLMPageResult


class PDFRowNormalizer:
    @staticmethod
    def normalize_row(row: Dict[str, Any], source_page: int) -> Dict[str, Any]:
        return {
            "tag": clean_string(row.get("tag")),
            "material_type": clean_string(row.get("material_type")) or "Window",
            "width": clean_string(row.get("width")),
            "height": clean_string(row.get("height")),
            "area": clean_string(row.get("area")),
            "quantity": clean_string(row.get("quantity")),
            "opening_type": clean_string(row.get("opening_type")),
            "material": clean_string(row.get("material")),
            "u_value": clean_string(row.get("u_value")),
            "shgc": clean_string(row.get("shgc")),
            "vt": clean_string(row.get("vt")),
            "glass_type": clean_string(row.get("glass_type")),
            "confidence": float(row.get("confidence", 0.0) or 0.0),
            "notes": clean_string(row.get("notes")),
            "source_page": source_page,
            "source_type": "pdf_langchain_crop_agent",
            "original_extraction": row,
        }

    def merge_and_normalize(self, llm_results: List[LLMPageResult]) -> List[Dict[str, Any]]:
        log_section("7. Merge + normalize extracted rows")
        rows: List[Dict[str, Any]] = []

        for result in llm_results:
            if not result.contains_schedule:
                continue
            for row in result.extracted_rows:
                normalized = self.normalize_row(row, source_page=result.page_number)
                rows.append(normalized)

        # Lightweight deduplication: same tag + dimensions + page.
        deduped: List[Dict[str, Any]] = []
        seen = set()
        for row in rows:
            key = (
                row.get("source_page"),
                row.get("tag"),
                row.get("width"),
                row.get("height"),
                row.get("quantity"),
            )
            if key in seen:
                continue
            seen.add(key)
            deduped.append(row)

        for row in deduped:
            log_debug(
                f"Row source_page={row['source_page']}: tag={row['tag']}, width={row['width']}, "
                f"height={row['height']}, qty={row['quantity']}, u={row['u_value']}, "
                f"confidence={row['confidence']}"
            )

        return deduped
