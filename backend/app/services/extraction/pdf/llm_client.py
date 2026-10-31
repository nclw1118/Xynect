"""LangChain ChatOpenAI wrapper.

Sources API key + model from settings (via PDFExtractionConfig).
No hard-coded credentials.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List

from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI

from app.services.extraction.pdf.config import PDFExtractionConfig


def _supports_custom_temperature(model: str) -> bool:
    """Whether `model` accepts a non-default `temperature`.

    Reasoning-class models reject anything other than the default temperature=1
    (e.g. gpt-5 non-chat, o1/o3/o4) and 400 if a value like 0 is sent. Mirrors
    the guard in app.services.llm.openai_provider so the vision path here behaves
    the same instead of erroring on current gpt-5.x models.
    """
    m = model.lower()
    if m.startswith(("o1", "o3", "o4")):
        return False
    if m.startswith("gpt-5") and "chat" not in m:
        return False
    return True


class LangChainLLMClient:
    """Wraps ChatOpenAI + structured-output + multimodal invocation."""

    def __init__(self, config: PDFExtractionConfig, reasoning_effort: str | None = None):
        api_key = (config.openai_api_key or "").strip()
        if not api_key:
            raise RuntimeError(
                "OpenAI API key is not set. Configure OPENAI_API_KEY in your .env file."
            )

        # LangChain integrations frequently read from this env var; preserve
        # the side effect from the original prototype to avoid surprise failures.
        os.environ["OPENAI_API_KEY"] = api_key

        llm_kwargs: Dict[str, Any] = {
            "model": config.llm_model,
            "api_key": api_key,
        }
        if reasoning_effort:
            llm_kwargs["reasoning_effort"] = reasoning_effort

        # temperature=0 is only sent when the model supports a custom value AND
        # (for reasoning models) effort is "none". Any higher reasoning effort
        # rejects a custom temperature with a 400, so we omit it and let the
        # model use its default.
        allow_custom_temp = _supports_custom_temperature(config.llm_model)
        if reasoning_effort not in (None, "none"):
            allow_custom_temp = False
        if allow_custom_temp:
            llm_kwargs["temperature"] = 0

        self._llm = ChatOpenAI(**llm_kwargs)
        self._model_name = config.llm_model
        self._reasoning_effort = reasoning_effort

    @property
    def reasoning_effort(self) -> str | None:
        return self._reasoning_effort

    @property
    def model_name(self) -> str:
        return self._model_name

    def with_structured_output(self, schema):
        return self._llm.with_structured_output(schema)

    @staticmethod
    def invoke_multimodal(structured_llm: Any, prompt: str, image_data_uris: List[str]) -> Any:
        content: List[Dict[str, Any]] = [{"type": "text", "text": prompt}]
        for uri in image_data_uris:
            content.append({
                "type": "image_url",
                "image_url": {
                    "url": uri,
                    "detail": "high",
                },
            })
        return structured_llm.invoke([HumanMessage(content=content)])
