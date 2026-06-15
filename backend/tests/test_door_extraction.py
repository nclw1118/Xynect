"""DB-free unit tests for M1 door support: dataclass, schemas, PDF schema, normalizer."""

from __future__ import annotations

from app.schemas.extraction import (
    DoorItemSchema,
    ExtractionResponse,
    PatchDoorItem,
    PatchExtractionRequest,
)
from app.services.extraction.spreadsheet_parser import ExtractionResult
from app.services.extraction.pdf.schemas import ExtractionPageResponse
from app.services.extraction.pdf.models import LLMPageResult
from app.services.extraction.pdf.row_normalizer import PDFRowNormalizer


# ── ExtractionResult dataclass ─────────────────────────────────────────────────

def test_extraction_result_defaults_door_rows_empty():
    res = ExtractionResult(window_rows=[])
    assert res.door_rows == []


def test_extraction_result_accepts_door_rows():
    res = ExtractionResult(
        window_rows=[{"tag": "W-1"}],
        door_rows=[{"tag": "D-1"}],
    )
    assert res.window_rows == [{"tag": "W-1"}]
    assert res.door_rows == [{"tag": "D-1"}]


# ── API schemas ────────────────────────────────────────────────────────────────

def test_extraction_response_door_items_default_empty():
    resp = ExtractionResponse(session_id="s", window_items=[], warnings=[])
    assert resp.door_items == []


def test_patch_extraction_request_supports_door_items():
    req = PatchExtractionRequest(
        door_items=[PatchDoorItem(id="d1", fire_rating="90 MIN", self_closing="YES")]
    )
    assert req.door_items is not None
    assert req.door_items[0].id == "d1"
    assert req.door_items[0].fire_rating == "90 MIN"


def test_door_item_schema_has_door_fields_not_nfrc():
    fields = DoorItemSchema.model_fields.keys()
    for f in ("fire_rating", "self_closing", "opening_type", "glass_type"):
        assert f in fields, f
    for f in ("u_value", "shgc", "vt"):
        assert f not in fields, f


# ── PDF structured-output schema ───────────────────────────────────────────────

def test_extraction_page_response_parses_window_and_door_rows():
    payload = {
        "page_number": 4,
        "page_classification": {
            "contains_schedule": True,
            "schedule_type": "mixed_door_window_schedule",
            "confidence": 0.9,
            "reason": "combined",
        },
        "window_rows": [
            {
                "tag": "W-1", "material_type": "Window", "width": "3'-0\"", "height": "4'-0\"",
                "area": "", "quantity": "2", "opening_type": "Fixed", "material": "Vinyl",
                "u_value": "0.30", "shgc": "0.25", "vt": "0.5", "glass_type": "Low-E",
                "confidence": 0.9, "notes": "",
            }
        ],
        "door_rows": [
            {
                "tag": "D-1", "opening_type": "Single", "quantity": "1", "width": "3'-0\"",
                "height": "7'-0\"", "material": "Steel", "fire_rating": "90 MIN",
                "self_closing": "YES", "glass_type": "", "notes": "exterior", "confidence": 0.88,
            }
        ],
        "warnings": [],
    }
    resp = ExtractionPageResponse.model_validate(payload)
    assert len(resp.window_rows) == 1
    assert len(resp.door_rows) == 1
    # Door rows have no NFRC / area fields in the schema.
    door_fields = type(resp.door_rows[0]).model_fields.keys()
    assert "u_value" not in door_fields
    assert "area" not in door_fields


# ── Row normalizer separation ──────────────────────────────────────────────────

def _result_with(window_rows, door_rows):
    return LLMPageResult(
        page_number=4,
        contains_schedule=True,
        schedule_type="mixed_door_window_schedule",
        confidence=0.9,
        reason="x",
        extracted_rows=window_rows,
        extracted_door_rows=door_rows,
    )


def test_normalizer_keeps_windows_and_doors_separate():
    res = _result_with(
        window_rows=[{"tag": "W-1", "material_type": "Window", "width": "3'", "height": "4'",
                      "u_value": "0.3", "quantity": "2", "confidence": 0.9}],
        door_rows=[{"tag": "D-1", "material_type": "Door", "width": "3'", "height": "7'",
                    "fire_rating": "90 MIN", "self_closing": "YES", "quantity": "1", "confidence": 0.8}],
    )
    norm = PDFRowNormalizer()
    windows = norm.merge_and_normalize([res])
    doors = norm.merge_and_normalize_doors([res])

    assert len(windows) == 1 and len(doors) == 1
    assert windows[0]["material_type"] == "Window"
    assert doors[0]["material_type"] == "Door"

    # Window rows carry NFRC, not door-only fields.
    assert "u_value" in windows[0]
    assert "fire_rating" not in windows[0]

    # Door rows carry door fields, not NFRC.
    assert windows[0]["tag"] == "W-1"
    assert doors[0]["tag"] == "D-1"
    assert doors[0]["fire_rating"] == "90 MIN"
    assert doors[0]["self_closing"] == "YES"
    assert "u_value" not in doors[0]


def test_normalizer_dedupes_doors_independently():
    # Two identical door rows on the same page collapse to one.
    door = {"tag": "D-1", "material_type": "Door", "width": "3'", "height": "7'",
            "quantity": "1", "confidence": 0.8}
    res = _result_with(window_rows=[], door_rows=[dict(door), dict(door)])
    doors = PDFRowNormalizer().merge_and_normalize_doors([res])
    assert len(doors) == 1


def test_normalizer_door_rows_present_even_if_no_windows():
    res = _result_with(
        window_rows=[],
        door_rows=[{"tag": "D-2", "material_type": "Door", "width": "3'", "height": "7'",
                    "quantity": "1", "confidence": 0.7}],
    )
    norm = PDFRowNormalizer()
    assert norm.merge_and_normalize([res]) == []
    assert len(norm.merge_and_normalize_doors([res])) == 1
