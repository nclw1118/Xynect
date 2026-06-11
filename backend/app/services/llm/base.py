"""
Abstract LLM provider interface.

PageClassification is the shared result type for classify_pages().
All providers must implement the four abstract methods.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class PageClassification:
    page_index: int
    page_type: str                        # see prompts.py for valid values
    page_title_detected: str | None = None
    title_block_sheet_title: str | None = None
    title_block_drawing_type: str | None = None
    contains_schedule_table: bool = False
    may_contain_window_or_opening_data: bool = False
    confidence: float = 0.5
    evidence: str | None = None


class LLMProvider(ABC):

    @abstractmethod
    def render_pages(self, content: bytes, file_type: str) -> list[str]:
        """Return list of base64-encoded PNG images."""
        ...

    @abstractmethod
    def classify_pages(self, pages: list[str]) -> list[PageClassification]:
        """Return a PageClassification for every page, in page_index order."""
        ...

    @abstractmethod
    def extract_project_info(self, pages: list[str]) -> dict:
        """Return project-level field dict. Empty dict if nothing found."""
        ...

    @abstractmethod
    def extract_window_schedule(self, pages: list[str]) -> list[dict]:
        """Return list of window row dicts. Empty list if nothing found."""
        ...
