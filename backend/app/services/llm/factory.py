"""
Returns the appropriate LLM provider based on settings.

In stub mode (LLM_PROVIDER=stub or OPENAI_API_KEY missing):
  → StubProvider — no API calls, safe mock data.

In openai mode (LLM_PROVIDER=openai + OPENAI_API_KEY set):
  → OpenAIProvider — real GPT-4.1 vision extraction.
"""

from app.core.config import settings
from app.services.llm.base import LLMProvider


def get_provider() -> LLMProvider:
    if settings.llm_provider == "openai":
        from app.services.llm.openai_provider import OpenAIProvider
        return OpenAIProvider()

    from app.services.llm.stub_provider import StubProvider
    return StubProvider()
