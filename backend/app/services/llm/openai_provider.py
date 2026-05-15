"""
Real OpenAI LLM provider (GPT-4.1 vision).

PDF pages are capped at MAX_PAGES to limit token usage.
All JSON output is validated with Pydantic; one retry is attempted on failure.
Area is NOT extracted from the model — the extraction agent calculates it deterministically.
"""

import base64
import io
import json
import re
from typing import Any

import fitz  # PyMuPDF
from openai import OpenAI
from pydantic import BaseModel, ValidationError, field_validator

from app.core.config import settings
from app.services.llm.base import LLMProvider, PageClassification
from app.services.llm.prompts import (
    JSON_RETRY_PROMPT,
    PAGE_CLASSIFICATION_SYSTEM,
    PAGE_CLASSIFICATION_USER,
    PROJECT_INFO_SYSTEM,
    PROJECT_INFO_USER,
    WINDOW_SCHEDULE_SYSTEM,
    WINDOW_SCHEDULE_USER,
)

MAX_PAGES = 20
_RENDER_DPI = 150


# ── Pydantic output models ─────────────────────────────────────────────────────

class _WindowRow(BaseModel):
    tag: str | None = None
    material_type: str = "Window"
    width: str | None = None
    height: str | None = None
    area: str | None = None        # always ignored — agent calculates deterministically
    quantity: str | None = None
    opening_type: str | None = None
    material: str | None = None
    u_value: str | None = None
    shgc: str | None = None
    vt: str | None = None
    glass_type: str | None = None
    confidence: float = 0.5
    notes: str | None = None

    @field_validator("confidence", mode="before")
    @classmethod
    def clamp_confidence(cls, v: Any) -> float:
        try:
            return max(0.0, min(1.0, float(v)))
        except (TypeError, ValueError):
            return 0.5

    @field_validator("material_type", mode="before")
    @classmethod
    def force_window(cls, _v: Any) -> str:
        return "Window"


class _ProjectInfo(BaseModel):
    project_name: str | None = None
    site_address: str | None = None
    city: str | None = None
    state: str | None = None
    zip_code: str | None = None
    detected_file_type: str | None = None
    detected_relevant_pages: dict | None = None


class _ExtractionOutput(BaseModel):
    project: _ProjectInfo = _ProjectInfo()
    windows: list[_WindowRow] = []
    warnings: list[str] = []


# Rich page classification models
class _RawPageClassification(BaseModel):
    page_index: int
    page_type: str
    page_title_detected: str | None = None
    title_block_sheet_title: str | None = None
    title_block_drawing_type: str | None = None
    contains_schedule_table: bool = False
    may_contain_window_or_opening_data: bool = False
    confidence: float = 0.5
    evidence: str | None = None


class _ClassificationOutput(BaseModel):
    pages: list[_RawPageClassification] = []


class _ProjectInfoOutput(BaseModel):
    project_name: str | None = None
    site_address: str | None = None
    city: str | None = None
    state: str | None = None
    zip_code: str | None = None


# ── Helpers ────────────────────────────────────────────────────────────────────

def _strip_json_fences(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _image_part(b64: str) -> dict:
    return {
        "type": "image_url",
        "image_url": {"url": f"data:image/png;base64,{b64}", "detail": "high"},
    }


def _call_with_retry(
    client: OpenAI,
    model: str,
    system: str,
    user_text: str,
    images: list[str],
    validator_cls: type[BaseModel],
) -> BaseModel:
    content_parts: list[dict] = [{"type": "text", "text": user_text}]
    for img in images:
        content_parts.append(_image_part(img))

    messages: list[dict] = [
        {"role": "system", "content": system},
        {"role": "user", "content": content_parts},
    ]

    for attempt in range(2):
        resp = client.chat.completions.create(
            model=model,
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0,
        )
        raw = resp.choices[0].message.content or ""
        cleaned = _strip_json_fences(raw)

        try:
            data = json.loads(cleaned)
            return validator_cls.model_validate(data)
        except (json.JSONDecodeError, ValidationError) as exc:
            if attempt == 0:
                messages.append({"role": "assistant", "content": raw})
                messages.append({"role": "user", "content": JSON_RETRY_PROMPT})
            else:
                raise ValueError(
                    f"OpenAI returned invalid JSON after retry. "
                    f"Error: {exc}. Response (truncated): {raw[:400]}"
                ) from exc

    raise ValueError("Unreachable")


# ── Provider ───────────────────────────────────────────────────────────────────

class OpenAIProvider(LLMProvider):

    def __init__(self) -> None:
        if not settings.openai_api_key:
            raise ValueError(
                "LLM_PROVIDER=openai is set but OPENAI_API_KEY is missing or empty. "
                "Set OPENAI_API_KEY in your .env file, or use LLM_PROVIDER=stub for development."
            )
        self._client = OpenAI(api_key=settings.openai_api_key)
        self._model = settings.llm_model or "gpt-4.1"

    def render_pages(self, content: bytes, file_type: str) -> list[str]:
        if file_type == "image":
            return [base64.b64encode(content).decode("utf-8")]

        doc = fitz.open(stream=io.BytesIO(content), filetype="pdf")
        pages: list[str] = []
        count = min(len(doc), MAX_PAGES)
        mat = fitz.Matrix(_RENDER_DPI / 72, _RENDER_DPI / 72)
        for i in range(count):
            pix = doc[i].get_pixmap(matrix=mat)
            pages.append(base64.b64encode(pix.tobytes("png")).decode("utf-8"))
        doc.close()
        return pages

    def classify_pages(self, pages: list[str]) -> list[PageClassification]:
        if not pages:
            return []
        result = _call_with_retry(
            self._client,
            self._model,
            PAGE_CLASSIFICATION_SYSTEM,
            PAGE_CLASSIFICATION_USER,
            pages,
            _ClassificationOutput,
        )
        assert isinstance(result, _ClassificationOutput)
        return [
            PageClassification(
                page_index=p.page_index,
                page_type=p.page_type,
                page_title_detected=p.page_title_detected,
                title_block_sheet_title=p.title_block_sheet_title,
                title_block_drawing_type=p.title_block_drawing_type,
                contains_schedule_table=p.contains_schedule_table,
                may_contain_window_or_opening_data=p.may_contain_window_or_opening_data,
                confidence=p.confidence,
                evidence=p.evidence,
            )
            for p in result.pages
        ]

    def extract_project_info(self, pages: list[str]) -> dict:
        if not pages:
            return {}
        result = _call_with_retry(
            self._client,
            self._model,
            PROJECT_INFO_SYSTEM,
            PROJECT_INFO_USER,
            pages[:3],
            _ProjectInfoOutput,
        )
        assert isinstance(result, _ProjectInfoOutput)
        return result.model_dump(exclude_none=True)

    def extract_window_schedule(self, pages: list[str]) -> list[dict]:
        if not pages:
            return []
        result = _call_with_retry(
            self._client,
            self._model,
            WINDOW_SCHEDULE_SYSTEM,
            WINDOW_SCHEDULE_USER,
            pages,
            _ExtractionOutput,
        )
        assert isinstance(result, _ExtractionOutput)
        rows = []
        for row in result.windows:
            d = row.model_dump()
            d.pop("area", None)   # always discard LLM area — agent calculates it
            rows.append(d)
        return rows
