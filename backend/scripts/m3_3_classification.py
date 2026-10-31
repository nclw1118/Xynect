#!/usr/bin/env python3
"""
M3.3 prototype — elevation-first, tag-guided classification on ONE elevation.

Phase A of the elevation roadmap. Standalone; consumes M3.2 output
(m3_2_<dir>_result.json: detected openings) + M3.1 tags + the extracted schedule
catalog. Emits results for MANUAL eval — it does not score.

Classification hierarchy (priority order), per the agreed design:
  1. explicit_tag          — opening has an associated visible tag (deterministic).
  2. elevation_visual_match — untagged opening visually matches a tagged reference
                              opening on THIS elevation (geometry/panels/mullions);
                              vertical alignment is SUPPORTING evidence, verified.
  3. schedule_match         — only if no elevation reference matches; compare to the
                              extracted catalog attributes.
  4. unknown / ambiguous    — insufficient or conflicting evidence; never guessed.

Core principle: classification is SEPARATE from counting. Every detected opening is
preserved in the output; an unresolved classification never removes an opening.

Outputs into the session debug dir:
  m3_3_<dir>_result.json    every opening + classification fields + coverage metrics
  m3_3_<dir>_overlay.png    boxes labeled by assigned type, colored by method

Usage (from backend/):
  python scripts/m3_3_classification.py --direction west --page 10
"""
from __future__ import annotations

import argparse
import base64
import dataclasses
import io
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional

from PIL import Image, ImageDraw, ImageFont
from pydantic import BaseModel, Field

SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_ROOT = SCRIPT_DIR.parent
PROJECT_ROOT = BACKEND_ROOT.parent
sys.path.insert(0, str(BACKEND_ROOT))

from app.services.extraction.pdf.config import PDFExtractionConfig  # noqa: E402
from app.services.extraction.pdf.cost_tracker import CostTracker  # noqa: E402
from app.services.extraction.pdf.llm_client import LangChainLLMClient  # noqa: E402

DEFAULT_SESSION = "329c4b8d-98a5-4635-9c89-d79865900fa8"
COLUMN_TOL = 0.015  # x-center tolerance for "same column" reference hints


# ── Structured output (untagged openings only) ───────────────────────────────
class UntaggedClassification(BaseModel):
    instance_id: str
    assigned_type: Optional[str] = Field(description="Schedule tag e.g. 'W2','G1', or null if unknown/ambiguous.")
    classification_method: str = Field(description="elevation_visual_match | schedule_match | unknown | ambiguous")
    reference_instance_id: Optional[str] = Field(default=None, description="tagged opening used as the visual reference, if any.")
    supporting_evidence: str = ""
    review_status: str = Field(description="accepted | pending_verification | needs_review")
    confidence: float = 0.0


class ClassifyResponse(BaseModel):
    classifications: List[UntaggedClassification]


# ── Catalog ──────────────────────────────────────────────────────────────────
def load_catalog_attrs(result_path: Path) -> Dict[str, dict]:
    d = json.loads(result_path.read_text())
    out: Dict[str, dict] = {}
    for r in d.get("extracted_window_rows", []):
        if r.get("tag"):
            out[r["tag"]] = {"kind": "window", "type": r.get("opening_type"),
                             "width": r.get("width"), "height": r.get("height")}
    for r in d.get("extracted_door_rows", []):
        if r.get("tag"):
            out[r["tag"]] = {"kind": "door", "type": r.get("opening_type"),
                             "width": r.get("width"), "height": r.get("height")}
    return out


# ── Geometry ─────────────────────────────────────────────────────────────────
def cx(b):  # x-center
    return (b[0] + b[2]) / 2


def column_reference_types(untagged, tagged) -> Dict[str, List[dict]]:
    """For each untagged opening, the tagged openings in the same vertical column
    (x-center within tolerance) — supporting evidence for visual matching."""
    hints: Dict[str, List[dict]] = {}
    for u in untagged:
        ux = cx(u["bbox"])
        refs = [{"instance_id": t["instance_id"], "type": t["visible_tag"]}
                for t in tagged if abs(cx(t["bbox"]) - ux) <= COLUMN_TOL]
        # de-dup by type keeping first instance of each
        seen, uniq = set(), []
        for r in refs:
            if r["type"] not in seen:
                seen.add(r["type"]); uniq.append(r)
        hints[u["instance_id"]] = uniq
    return hints


# ── Prompt ───────────────────────────────────────────────────────────────────
def build_prompt(direction, tagged, untagged, hints, catalog) -> str:
    refs = [{"instance_id": t["instance_id"], "type": t["visible_tag"],
             "floor": t["floor"], "bbox": t["bbox"]} for t in tagged]
    to_classify = [{"instance_id": u["instance_id"], "floor": u["floor"], "bbox": u["bbox"],
                    "object_category": u["object_category"],
                    "same_column_reference_hints": hints.get(u["instance_id"], [])}
                   for u in untagged]
    return f"""
You are classifying openings on ONE building elevation ({direction.upper()}),
ELEVATION-FIRST. The image shows every detected opening as a numbered box: boxes
labeled with a type (e.g. "12:W2") are REFERENCE openings that carry an explicit
tag; boxes labeled "n:?" are the ones you must classify.

Classify each opening in "openings_to_classify" using this strict priority:
1. elevation_visual_match: assign the type of a REFERENCE opening on THIS elevation
   that this opening visually matches — same overall geometry, proportions, panel
   layout, mullion arrangement, configuration. Vertically aligned / repeated
   openings are SUPPORTING evidence (see same_column_reference_hints) — VERIFY the
   visual characteristics, do not assume alignment alone. Set reference_instance_id.
2. schedule_match: ONLY if no elevation reference matches, compare to the schedule
   catalog attributes and choose the best-supported type.
3. unknown / ambiguous: if evidence is insufficient or conflicting. Do NOT guess a
   type merely to complete the inventory. Never override an explicit tag.

Set review_status: accepted (clear match), pending_verification (likely but worth a
look), or needs_review (weak/conflicting). Return one entry per opening to classify.

REFERENCE openings (explicitly tagged): {json.dumps(refs)}
openings_to_classify: {json.dumps(to_classify)}
SCHEDULE CATALOG (fallback only): {json.dumps(catalog)}
""".strip()


# ── Overlay ──────────────────────────────────────────────────────────────────
def _font(size: int):
    try:
        return ImageFont.load_default(size=size)
    except Exception:
        return ImageFont.load_default()


METHOD_COLOR = {
    "explicit_tag": (20, 160, 60),           # green
    "elevation_visual_match": (30, 120, 220),  # blue
    "schedule_match": (150, 40, 200),        # purple
    "unknown": (220, 30, 30),                # red
    "ambiguous": (220, 30, 30),
}


def numbered_input_image(crop_png: Path, openings: List[dict]) -> str:
    """Elevation with each opening boxed + 'n:type' (tagged) or 'n:?' (untagged)."""
    im = Image.open(crop_png).convert("RGB")
    W, H = im.size
    draw = ImageDraw.Draw(im, "RGBA")
    lw = max(2, W // 700)
    font = _font(max(13, W // 110))
    for o in openings:
        x0, y0, x1, y1 = o["bbox"][0] * W, o["bbox"][1] * H, o["bbox"][2] * W, o["bbox"][3] * H
        tagged = o["tag_status"] == "explicit"
        c = (20, 160, 60) if tagged else (120, 120, 120)
        draw.rectangle([x0, y0, x1, y1], outline=c + (255,), width=lw)
        lbl = f"{o['n']}:{o['visible_tag']}" if tagged else f"{o['n']}:?"
        draw.text((x0 + 2, y0 + 2), lbl, fill=c, font=font)
    buf = io.BytesIO(); im.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def draw_output_overlay(crop_png: Path, out_png: Path, openings: List[dict]) -> None:
    im = Image.open(crop_png).convert("RGB")
    W, H = im.size
    draw = ImageDraw.Draw(im, "RGBA")
    lw = max(2, W // 650)
    font = _font(max(13, W // 110))
    for o in openings:
        c = METHOD_COLOR.get(o["classification_method"], (220, 30, 30))
        x0, y0, x1, y1 = o["bbox"][0] * W, o["bbox"][1] * H, o["bbox"][2] * W, o["bbox"][3] * H
        draw.rectangle([x0, y0, x1, y1], outline=c + (255,), width=lw)
        draw.text((x0 + 2, y0 + 2), o["assigned_type"] or "?", fill=c, font=font)
    im.save(out_png)


# ── Main ─────────────────────────────────────────────────────────────────────
def main() -> None:
    ap = argparse.ArgumentParser(description="M3.3 elevation-first classification prototype")
    ap.add_argument("--session", default=DEFAULT_SESSION)
    ap.add_argument("--page", type=int, default=10)
    ap.add_argument("--direction", default="west")
    ap.add_argument("--model", default="gpt-6.1-terra")
    ap.add_argument("--effort", default="medium")
    args = ap.parse_args()

    debug_dir = BACKEND_ROOT / "storage" / "extraction_debug" / args.session
    crop_png = debug_dir / f"elevation_page_{args.page:03d}_{args.direction}.png"
    m32_path = debug_dir / f"m3_2_{args.direction}_result.json"
    result_path = debug_dir / "extraction_result.json"
    for p in (crop_png, m32_path, result_path):
        if not p.exists():
            raise SystemExit(f"Missing input: {p} (run m3_2_opening_detection.py first)")

    m32 = json.loads(m32_path.read_text())
    openings = m32["openings"]
    catalog = load_catalog_attrs(result_path)

    tagged = [o for o in openings if o["tag_status"] == "explicit"]
    untagged = [o for o in openings if o["tag_status"] != "explicit"]
    hints = column_reference_types(untagged, tagged)

    # 1. explicit_tag — deterministic
    cls: Dict[str, dict] = {}
    for o in tagged:
        cls[o["instance_id"]] = {
            "assigned_type": o["visible_tag"], "classification_method": "explicit_tag",
            "reference_instance_id": o["instance_id"],
            "supporting_evidence": "Opening carries an explicit tag.",
            "review_status": "accepted", "confidence": 1.0,
        }

    # 2–4. untagged via LLM (elevation-first, schedule fallback)
    if untagged:
        config = dataclasses.replace(PDFExtractionConfig.from_settings(), llm_model=args.model)
        cost = CostTracker(session_id=args.session, model=args.model)
        client = LangChainLLMClient(config, reasoning_effort=args.effort,
                                    stage="m3_3_classification", cost_tracker=cost)
        structured = client.with_structured_output(ClassifyResponse)
        uri = "data:image/png;base64," + numbered_input_image(crop_png, openings)
        prompt = build_prompt(args.direction, tagged, untagged, hints, catalog)
        print(f"[m3.3] classifying {len(untagged)} untagged openings "
              f"({len(tagged)} explicit refs), model={args.model} effort={args.effort}")
        resp: ClassifyResponse = client.invoke_multimodal(structured, prompt, [uri],
                                                          label=f"{args.direction}_classify")
        returned = {c.instance_id: c for c in resp.classifications}
        for o in untagged:
            c = returned.get(o["instance_id"])
            if c is None:  # model omitted it — preserve as unknown, never drop
                cls[o["instance_id"]] = {
                    "assigned_type": None, "classification_method": "unknown",
                    "reference_instance_id": None,
                    "supporting_evidence": "No classification returned by model.",
                    "review_status": "needs_review", "confidence": 0.0,
                }
            else:
                cls[o["instance_id"]] = {
                    "assigned_type": c.assigned_type,
                    "classification_method": c.classification_method,
                    "reference_instance_id": c.reference_instance_id,
                    "supporting_evidence": c.supporting_evidence,
                    "review_status": c.review_status, "confidence": c.confidence,
                }
        totals = cost.to_dict()["totals"]
    else:
        totals = {"cost_usd": 0.0, "input_tokens": 0, "cached_input_tokens": 0,
                  "output_tokens": 0, "reasoning_tokens": 0}

    # merge classification onto every detected opening (counting preserved)
    classified = []
    for o in openings:
        merged = dict(o)
        merged.update(cls.get(o["instance_id"], {
            "assigned_type": None, "classification_method": "unknown",
            "reference_instance_id": None, "supporting_evidence": "",
            "review_status": "needs_review", "confidence": 0.0}))
        classified.append(merged)

    # ── Metrics ──────────────────────────────────────────────────────────────
    total = len(classified)
    method_counts = Counter(c["classification_method"] for c in classified)
    elevation_first = method_counts["explicit_tag"] + method_counts["elevation_visual_match"]
    type_counts = Counter(c["assigned_type"] for c in classified if c["assigned_type"])
    unresolved = [c["instance_id"] for c in classified
                  if c["classification_method"] in ("unknown", "ambiguous")]

    out = {
        "session_id": args.session, "page": args.page, "direction": args.direction,
        "model": args.model, "reasoning_effort": args.effort,
        "total_openings": total,
        "method_breakdown": dict(method_counts),
        "elevation_first_coverage": round(elevation_first / total, 4) if total else 0.0,
        "assigned_type_counts": dict(type_counts),
        "unresolved_instance_ids": unresolved,
        "openings": classified,
        "llm_cost_usd": totals["cost_usd"],
        "llm_tokens": {k: totals[k] for k in
                       ("input_tokens", "cached_input_tokens", "output_tokens", "reasoning_tokens")},
    }
    out_json = debug_dir / f"m3_3_{args.direction}_result.json"
    out_json.write_text(json.dumps(out, indent=2))
    out_png = debug_dir / f"m3_3_{args.direction}_overlay.png"
    draw_output_overlay(crop_png, out_png, classified)

    # ── Summary ───────────────────────────────────────────────────────────────
    print(f"[m3.3] {total} openings | elevation-first coverage="
          f"{out['elevation_first_coverage']*100:.1f}% | cost=${totals['cost_usd']:.6f}")
    print(f"[m3.3] methods: {dict(method_counts)}")
    print(f"[m3.3] type counts: {dict(type_counts)}")
    if unresolved:
        print(f"[m3.3] unresolved ({len(unresolved)}): {unresolved}")
    print(f"[written] {out_json}")
    print(f"[written] {out_png}")


if __name__ == "__main__":
    main()
