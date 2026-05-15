"""
Stub LLM provider — returns safe mock data without any API calls.
Used when LLM_PROVIDER=stub or OPENAI_API_KEY is not set.
"""

from app.services.llm.base import LLMProvider, PageClassification

_STUB_NOTE = "Stub data — PDF/image extraction requires LLM_PROVIDER=openai with a valid OPENAI_API_KEY."


class StubProvider(LLMProvider):

    def render_pages(self, content: bytes, file_type: str) -> list[str]:
        return []

    def classify_pages(self, pages: list[str]) -> list[PageClassification]:
        return [
            PageClassification(
                page_index=i,
                page_type="window_schedule",
                contains_schedule_table=True,
                may_contain_window_or_opening_data=True,
                confidence=0.5,
                evidence="Stub classification",
            )
            for i in range(len(pages))
        ]

    def extract_project_info(self, pages: list[str]) -> dict:
        return {}

    def extract_window_schedule(self, pages: list[str]) -> list[dict]:
        return [
            {
                "material_type": "Window",
                "tag": "W1",
                "confidence": 0.0,
                "notes": _STUB_NOTE,
            },
            {
                "material_type": "Window",
                "tag": "W2",
                "confidence": 0.0,
                "notes": _STUB_NOTE,
            },
        ]
