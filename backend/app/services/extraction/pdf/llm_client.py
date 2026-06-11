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


class LangChainLLMClient:
    """Wraps ChatOpenAI + structured-output + multimodal invocation."""

    def __init__(self, config: PDFExtractionConfig):
        api_key = (config.openai_api_key or "").strip()
        if not api_key:
            raise RuntimeError(
                "OpenAI API key is not set. Configure OPENAI_API_KEY in your .env file."
            )

        # LangChain integrations frequently read from this env var; preserve
        # the side effect from the original prototype to avoid surprise failures.
        os.environ["OPENAI_API_KEY"] = api_key

        self._llm = ChatOpenAI(
            model=config.llm_model,
            api_key=api_key,
            temperature=0,
        )
        self._model_name = config.llm_model

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
