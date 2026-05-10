"""
Deterministic Excel/CSV extraction.

- No LLM calls.
- Parses only explicitly present columns.
- Missing fields remain empty (never invented).
- Confidence per row = average of per-column confidence scores.
"""

import io
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from app.services.extraction.column_mapping import map_headers
from app.services.extraction.normalizers import normalize_value


@dataclass
class ExtractionResult:
    window_rows: list[dict]
    warnings: list[str] = field(default_factory=list)
    project_info: dict | None = None  # always None for spreadsheets


def parse_spreadsheet(content: bytes, filename: str) -> ExtractionResult:
    """
    Parse a CSV, XLSX, or XLS file and return normalized window rows.
    Raises ValueError with a user-friendly message on unrecoverable errors.
    """
    ext = Path(filename).suffix.lower()
    warnings: list[str] = []

    # ── Read into DataFrame ───────────────────────────────────────────────
    try:
        if ext == ".csv":
            df = pd.read_csv(io.BytesIO(content), dtype=str, keep_default_na=False)
        else:
            df = pd.read_excel(
                io.BytesIO(content),
                dtype=str,
                keep_default_na=False,
                engine="openpyxl" if ext == ".xlsx" else "xlrd",
            )
    except Exception as exc:
        raise ValueError(f"Could not read spreadsheet: {exc}") from exc

    # Strip whitespace from all headers
    df.columns = [str(c).strip() for c in df.columns]

    if df.empty or len(df.columns) == 0:
        raise ValueError("Spreadsheet appears to be empty.")

    # Drop entirely-blank rows early
    df = df.dropna(how="all")
    df = df[~df.apply(lambda row: all(str(v).strip() == "" for v in row), axis=1)]
    if df.empty:
        raise ValueError("Spreadsheet has no data rows after removing blank rows.")

    # ── Map column headers ────────────────────────────────────────────────
    header_map, mapping_warnings = map_headers(list(df.columns))
    warnings.extend(mapping_warnings)

    if not header_map:
        raise ValueError(
            "No recognizable column headers found. "
            "Accepted headers include: TAG, TYPE, WIDTH(FT), HEIGHT, QTY, U-VALUE, AREA(SF), etc."
        )

    # ── Build window rows ─────────────────────────────────────────────────
    rows: list[dict] = []
    for _, raw_row in df.iterrows():
        item: dict = {"material_type": "Window"}
        confidence_scores: list[float] = []

        for src_col, mapping in header_map.items():
            raw_val = str(raw_row.get(src_col, "")).strip()
            if not raw_val:
                continue  # leave field absent (will remain None in DB)

            normalized = normalize_value(mapping.field, raw_val, mapping.unit)
            if normalized:
                item[mapping.field] = normalized
                confidence_scores.append(mapping.confidence)

        # Skip rows that have no data beyond material_type
        if len(item) <= 1:
            continue

        item["confidence"] = (
            round(sum(confidence_scores) / len(confidence_scores), 3)
            if confidence_scores
            else 0.5
        )

        rows.append(item)

    if not rows:
        raise ValueError(
            "No window rows could be extracted. "
            "The spreadsheet may not contain recognizable window schedule data."
        )

    return ExtractionResult(window_rows=rows, warnings=warnings, project_info=None)
