"""
Stub extractor for PDF and image files.

Returns clearly-marked placeholder rows so the full flow can be tested
without OpenAI integration. Real LLM extraction is Phase 5+.
"""

from app.services.extraction.spreadsheet_parser import ExtractionResult

_STUB_NOTE = "Stub data — PDF/image extraction requires OpenAI integration (Phase 5+)."

_STUB_WARNING = (
    "PDF and image extraction is not yet available. "
    "The rows below are placeholder data so you can test the review flow. "
    "Real extraction will be enabled when LLM_PROVIDER=openai is configured."
)


def extract_stub(file_type: str) -> ExtractionResult:
    rows = [
        {
            "material_type": "Window",
            "tag": "W1",
            "width": None,
            "height": None,
            "quantity": None,
            "confidence": 0.0,
            "notes": _STUB_NOTE,
        },
        {
            "material_type": "Window",
            "tag": "W2",
            "width": None,
            "height": None,
            "quantity": None,
            "confidence": 0.0,
            "notes": _STUB_NOTE,
        },
    ]
    return ExtractionResult(
        window_rows=rows,
        warnings=[_STUB_WARNING],
        project_info=None,
    )
