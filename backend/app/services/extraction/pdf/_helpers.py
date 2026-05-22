"""Shared helpers used across the PDF extraction package.

Logging/text/image helpers ported verbatim from NOTEBOOKS/pdf_algo_test.py.
"""

from __future__ import annotations

import base64
import re
from pathlib import Path


# ── Logging (uses print to mirror the standalone prototype output) ────────────

def log_section(title: str) -> None:
    print("\n" + "=" * 88)
    print(title)
    print("=" * 88)


def log_step(message: str) -> None:
    print(f"[STEP] {message}")


def log_debug(message: str) -> None:
    print(f"  - {message}")


# ── Text helpers ──────────────────────────────────────────────────────────────

def preview_text(text: str, max_chars: int = 700) -> str:
    cleaned = re.sub(r"\s+", " ", text or "").strip()
    if len(cleaned) <= max_chars:
        return cleaned
    return cleaned[:max_chars] + "..."


def normalize_for_matching(s: str) -> str:
    s = s.upper()
    s = s.replace("&", " AND ")
    s = re.sub(r"[^A-Z0-9\-\.\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def clean_string(value) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


# ── Image / data-uri helpers ──────────────────────────────────────────────────

def png_bytes_to_data_uri(png_bytes: bytes) -> str:
    b64 = base64.b64encode(png_bytes).decode("utf-8")
    return f"data:image/png;base64,{b64}"


def path_to_data_uri(path: str | Path) -> str:
    data = Path(path).read_bytes()
    return png_bytes_to_data_uri(data)
