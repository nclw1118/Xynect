"""Writes extraction_result.json + manages the per-session debug directory.

The PNG artifacts (rendered pages, crops, overlays) are written by PDFRenderer
into the directory returned by `ensure_session_dir`. This writer just adds the
final JSON summary.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from app.services.extraction.pdf._helpers import log_debug
from app.services.extraction.pdf.config import PDFExtractionConfig
from app.services.extraction.pdf.models import PDFExtractionArtifacts


class PDFExtractionDebugWriter:
    def __init__(self, config: PDFExtractionConfig):
        self.config = config

    def ensure_session_dir(self, session_id: str) -> Path:
        out_dir = Path(self.config.debug_output_dir) / session_id
        out_dir.mkdir(parents=True, exist_ok=True)
        return out_dir

    def write_result(self, out_dir: Path, artifacts: PDFExtractionArtifacts) -> Path | None:
        if not self.config.save_debug_artifacts:
            return None
        try:
            result_path = out_dir / "extraction_result.json"
            result_path.write_text(json.dumps(asdict(artifacts), indent=2), encoding="utf-8")
            log_debug(f"Saved result JSON: {result_path}")
            return result_path
        except Exception as exc:
            log_debug(f"Could not write extraction_result.json: {exc}")
            return None

    def write_fast_routing(self, out_dir: Path, payload: dict) -> Path | None:
        """Write the fast_page_routing.json debug artifact."""
        if not self.config.save_debug_artifacts:
            return None
        try:
            routing_path = out_dir / "fast_page_routing.json"
            routing_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            log_debug(f"Saved fast routing JSON: {routing_path}")
            return routing_path
        except Exception as exc:
            log_debug(f"Could not write fast_page_routing.json: {exc}")
            return None

    def write_elevation_regions(self, out_dir: Path, payload: dict) -> Path | None:
        """Write the elevation_regions.json debug artifact (M2)."""
        if not self.config.save_debug_artifacts:
            return None
        try:
            path = out_dir / "elevation_regions.json"
            path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            log_debug(f"Saved elevation regions JSON: {path}")
            return path
        except Exception as exc:
            log_debug(f"Could not write elevation_regions.json: {exc}")
            return None
