"""Shared helpers used across the PDF extraction package.

Logging/text/image helpers ported verbatim from NOTEBOOKS/pdf_algo_test.py.
"""

from __future__ import annotations

import base64
import contextvars
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, TextIO


# ── Logging (prints to stdout, and optionally tees to per-session files) ───────
#
# All pipeline logging goes through log_section/log_step/log_debug. Output is
# always printed (mirroring the standalone prototype) and, when a session log
# file is open, also written to that file. A ContextVar holds the active sinks
# so concurrent extractions (different threads / asyncio tasks) never mix logs.

_log_sinks: contextvars.ContextVar = contextvars.ContextVar("pdf_log_sinks", default=())


@dataclass
class _SessionLog:
    handle: TextIO
    token: object  # contextvars.Token returned by ContextVar.set()


def _emit(line: str) -> None:
    print(line)
    for fh in _log_sinks.get():
        try:
            fh.write(line + "\n")
            fh.flush()
        except Exception:
            # A broken sink must never break extraction.
            pass


def open_session_log(path: "str | Path") -> Optional[_SessionLog]:
    """Start teeing log output to `path` for the current execution context.

    Returns a handle to pass to close_session_log(), or None if the file could
    not be opened (logging then simply continues to stdout only).
    """
    try:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        fh = open(path, "w", encoding="utf-8")
    except Exception as exc:  # pragma: no cover - defensive
        print(f"  - Could not open session log file {path}: {exc}")
        return None
    token = _log_sinks.set(_log_sinks.get() + (fh,))
    return _SessionLog(handle=fh, token=token)


def close_session_log(session_log: Optional[_SessionLog]) -> None:
    """Stop teeing and close the file opened by open_session_log()."""
    if session_log is None:
        return
    try:
        _log_sinks.reset(session_log.token)
    except Exception:  # pragma: no cover - defensive
        pass
    try:
        session_log.handle.flush()
        session_log.handle.close()
    except Exception:  # pragma: no cover - defensive
        pass


def log_section(title: str) -> None:
    _emit("\n" + "=" * 88)
    _emit(title)
    _emit("=" * 88)


def log_step(message: str) -> None:
    _emit(f"[STEP] {message}")


def log_debug(message: str) -> None:
    _emit(f"  - {message}")


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
