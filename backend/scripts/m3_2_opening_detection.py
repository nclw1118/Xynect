#!/usr/bin/env python3
"""
M3.2 prototype — opening detection on ONE elevation (every window/door assembly,
tagged or not).

Phase A of the elevation roadmap. Standalone; consumes M3.1 output
(m3_1_<dir>_result.json: floor bands + deterministic tags) plus the elevation
crop PNG. Emits results for MANUAL eval — it does not score.

Design (matches the agreed plan):
- Detection is INDEPENDENT of tags: the model is asked to find every physical
  window/door assembly, so untagged openings are not overlooked.
- Per-floor-region: each has_openings band is cropped (with vertical margin) and
  detected separately — better bbox precision and avoids large-image instability.
- Tags are associated DETERMINISTICALLY afterwards (a tag whose center falls
  inside a detected box → that box is 'explicit'; boxes with none → 'untagged').
- Detections across the overlap margins are de-duplicated by IoU.

Outputs into the session debug dir:
  m3_2_<dir>_result.json   one record per detected opening (+ per-floor totals)
  m3_2_<dir>_overlay.png   numbered box around every detected assembly

Usage (from backend/):
  python scripts/m3_2_opening_detection.py --direction west --page 10
  python scripts/m3_2_opening_detection.py --effort high
"""
from __future__ import annotations

import argparse
import base64
import dataclasses
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional, Tuple

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
MARGIN_FRAC = 0.25   # vertical overlap margin added above/below each floor band
IOU_DEDUP = 0.5      # detections overlapping more than this across floors are merged


# ── Structured output ────────────────────────────────────────────────────────
class Opening(BaseModel):
    bbox: List[float] = Field(description="[x0,y0,x1,y1] normalized 0..1 within THIS floor-strip image.")
    object_category: str = Field(description="'window' or 'door' by appearance only (do not infer the tag/type).")
    confidence: float = 0.0
    needs_review: bool = Field(default=False, description="true if partially occluded, cut off, or ambiguous.")
    review_reason: str = ""


class FloorOpenings(BaseModel):
    openings: List[Opening]


# ── Prompt ───────────────────────────────────────────────────────────────────
def build_prompt(direction: str, floor_name: str, scale: str) -> str:
    return f"""
You are detecting physical window and door ASSEMBLIES in a horizontal strip of a
building elevation drawing (direction: {direction.upper()}, floor: {floor_name},
scale: {scale}). The strip may include small slivers of the floors above/below —
only detect assemblies that belong to THIS floor row.

Return ONE bounding box per COMPLETE assembly:
- Detect EVERY visible window and door opening, whether or not it carries a tag.
  Untagged openings matter exactly as much as tagged ones — do not skip them.
- One box per whole assembly. Do NOT split an assembly into separate panes,
  lites, mullions, sidelites, transoms, or balcony rails. A multi-pane window is
  ONE assembly. A balcony glass door is one assembly (the railing is NOT an opening).
- Classify object_category as 'window' or 'door' by appearance only. Do NOT infer
  tag names or schedule types (that is a later step).
- bbox is normalized 0..1 within THIS image.
- Set needs_review=true for anything partially occluded, cut off at the strip
  edge, or ambiguous, with a short review_reason.

Ignore: balcony railings, dimension lines/leaders, text labels, floor datum lines,
and anything that is not an actual window or door opening.
""".strip()


# ── Geometry helpers ─────────────────────────────────────────────────────────
def iou(a: List[float], b: List[float]) -> float:
    ax0, ay0, ax1, ay1 = a
    bx0, by0, bx1, by1 = b
    ix0, iy0 = max(ax0, bx0), max(ay0, by0)
    ix1, iy1 = min(ax1, bx1), min(ay1, by1)
    iw, ih = max(0.0, ix1 - ix0), max(0.0, iy1 - iy0)
    inter = iw * ih
    if inter <= 0:
        return 0.0
    area_a = max(0.0, ax1 - ax0) * max(0.0, ay1 - ay0)
    area_b = max(0.0, bx1 - bx0) * max(0.0, by1 - by0)
    return inter / (area_a + area_b - inter)


def center(b: List[float]) -> Tuple[float, float]:
    return (b[0] + b[2]) / 2, (b[1] + b[3]) / 2


def contains(box: List[float], pt: Tuple[float, float]) -> bool:
    return box[0] <= pt[0] <= box[2] and box[1] <= pt[1] <= box[3]


def floor_key(name: str) -> str:
    m = re.search(r"(\d+)(?:ST|ND|RD|TH)?_?FLOOR", name, re.I)
    if m:
        return f"{m.group(1)}f"
    return re.sub(r"[^a-z0-9]+", "", name.lower())[:6] or "x"


def band_for(bands: List[dict], y: float) -> dict | None:
    for b in bands:
        if b["y_top"] <= y <= b["y_bottom"]:
            return b
    return None


# ── Overlay ──────────────────────────────────────────────────────────────────
def _font(size: int):
    try:
        return ImageFont.load_default(size=size)
    except Exception:
        return ImageFont.load_default()


def draw_overlay(crop_png: Path, out_png: Path, detections: List[dict]) -> None:
    im = Image.open(crop_png).convert("RGB")
    W, H = im.size
    draw = ImageDraw.Draw(im, "RGBA")
    lw = max(2, W // 650)
    font = _font(max(13, W // 110))
    GREEN, ORANGE, YELLOW = (20, 160, 60), (220, 110, 0), (210, 170, 0)
    for d in detections:
        x0, y0, x1, y1 = (d["bbox"][0] * W, d["bbox"][1] * H, d["bbox"][2] * W, d["bbox"][3] * H)
        if d["needs_review"]:
            c = YELLOW
        elif d["tag_status"] == "explicit":
            c = GREEN
        else:
            c = ORANGE
        draw.rectangle([x0, y0, x1, y1], outline=c + (255,), width=lw)
        lbl = f"{d['n']}:{d['visible_tag']}" if d["visible_tag"] else f"{d['n']}:?"
        draw.text((x0 + 2, y0 + 2), lbl, fill=c, font=font)
    im.save(out_png)


# ── Main ─────────────────────────────────────────────────────────────────────
def main() -> None:
    ap = argparse.ArgumentParser(description="M3.2 opening detection prototype")
    ap.add_argument("--session", default=DEFAULT_SESSION)
    ap.add_argument("--page", type=int, default=10)
    ap.add_argument("--direction", default="west")
    ap.add_argument("--model", default="gpt-6.1-terra")
    ap.add_argument("--effort", default="high")
    args = ap.parse_args()

    debug_dir = BACKEND_ROOT / "storage" / "extraction_debug" / args.session
    crop_png = debug_dir / f"elevation_page_{args.page:03d}_{args.direction}.png"
    m31_path = debug_dir / f"m3_1_{args.direction}_result.json"
    for p in (crop_png, m31_path):
        if not p.exists():
            raise SystemExit(f"Missing input: {p} (run m3_1_elevation.py first)")

    m31 = json.loads(m31_path.read_text())
    bands = [b for b in m31["model_floors"]]
    open_bands = [b for b in bands if b.get("has_openings")]
    det_tags = m31.get("deterministic_tags", [])
    scale = m31.get("scale", "")

    im = Image.open(crop_png).convert("RGB")
    W, H = im.size

    config = dataclasses.replace(PDFExtractionConfig.from_settings(), llm_model=args.model)
    cost = CostTracker(session_id=args.session, model=args.model)
    client = LangChainLLMClient(config, reasoning_effort=args.effort,
                                stage="m3_2_opening_detection", cost_tracker=cost)
    structured = client.with_structured_output(FloorOpenings)

    print(f"[m3.2] {args.direction} p{args.page}: detecting over {len(open_bands)} "
          f"opening floors, model={args.model} effort={args.effort}")

    raw: List[dict] = []  # detections in elevation-normalized coords (pre-dedup)
    for b in open_bands:
        yt, yb = b["y_top"], b["y_bottom"]
        m = (yb - yt) * MARGIN_FRAC
        cy0, cy1 = max(0.0, yt - m), min(1.0, yb + m)
        strip = im.crop((0, int(cy0 * H), W, int(cy1 * H)))
        uri = "data:image/png;base64," + _png_uri(strip)
        prompt = build_prompt(args.direction, b["name"], scale)
        resp: FloorOpenings = client.invoke_multimodal(structured, prompt, [uri], label=b["name"])
        for o in resp.openings:
            # map strip-normalized bbox → elevation-normalized (x unchanged; full width)
            ex0, ex1 = o.bbox[0], o.bbox[2]
            ey0 = cy0 + o.bbox[1] * (cy1 - cy0)
            ey1 = cy0 + o.bbox[3] * (cy1 - cy0)
            raw.append({
                "bbox": [round(ex0, 4), round(ey0, 4), round(ex1, 4), round(ey1, 4)],
                "object_category": o.object_category,
                "confidence": o.confidence,
                "needs_review": o.needs_review,
                "review_reason": o.review_reason,
                "source_floor": b["name"],
            })
        print(f"   {b['name']:16} -> {len(resp.openings)} openings")

    # ── Dedup across floor-crop overlaps (IoU) ────────────────────────────────
    raw.sort(key=lambda d: (-d["confidence"], center(d["bbox"])[1]))
    kept: List[dict] = []
    for d in raw:
        if any(iou(d["bbox"], k["bbox"]) > IOU_DEDUP for k in kept):
            continue
        kept.append(d)

    # ── Assign floor by center + deterministic tag association ─────────────────
    for d in kept:
        cx, cy = center(d["bbox"])
        band = band_for(bands, cy) or {"name": "UNASSIGNED"}
        d["floor"] = band["name"]
        tag = None
        for t in det_tags:
            if contains(d["bbox"], center(t["bbox"])):
                tag = t["tag"]
                break
        d["visible_tag"] = tag
        d["tag_status"] = "explicit" if tag else "untagged"

    # order top→bottom, left→right and assign instance ids + display numbers
    kept.sort(key=lambda d: (center(d["bbox"])[1], center(d["bbox"])[0]))
    per_floor_idx: Counter = Counter()
    for i, d in enumerate(kept, 1):
        d["n"] = i
        fk = floor_key(d["floor"])
        per_floor_idx[fk] += 1
        d["instance_id"] = f"{args.direction}_{fk}_{per_floor_idx[fk]:03d}"

    # ── Tags detected by M3.1 but not inside any opening (possible misses) ─────
    assigned_tag_centers = 0
    missed_tags = []
    for t in det_tags:
        if any(contains(d["bbox"], center(t["bbox"])) for d in kept):
            assigned_tag_centers += 1
        else:
            missed_tags.append({"tag": t["tag"], "pos": [t["x"], t["y"]]})

    # ── Per-floor summary ──────────────────────────────────────────────────────
    per_floor: Dict[str, Dict] = {}
    for d in kept:
        s = per_floor.setdefault(d["floor"], {"total": 0, "tagged": 0, "untagged": 0,
                                              "windows": 0, "doors": 0, "needs_review": 0})
        s["total"] += 1
        s["tagged" if d["tag_status"] == "explicit" else "untagged"] += 1
        s["windows" if d["object_category"] == "window" else "doors"] += 1
        s["needs_review"] += int(d["needs_review"])

    totals = cost.to_dict()["totals"]
    out = {
        "session_id": args.session, "page": args.page, "direction": args.direction,
        "model": args.model, "reasoning_effort": args.effort, "scale": scale,
        "total_openings": len(kept),
        "tagged_openings": sum(1 for d in kept if d["tag_status"] == "explicit"),
        "untagged_openings": sum(1 for d in kept if d["tag_status"] == "untagged"),
        "needs_review_count": sum(1 for d in kept if d["needs_review"]),
        "per_floor": per_floor,
        "m31_tags_total": len(det_tags),
        "m31_tags_matched_to_an_opening": assigned_tag_centers,
        "m31_tags_without_opening": missed_tags,
        "openings": kept,
        "llm_cost_usd": totals["cost_usd"],
        "llm_tokens": {k: totals[k] for k in
                       ("input_tokens", "cached_input_tokens", "output_tokens", "reasoning_tokens")},
    }
    out_json = debug_dir / f"m3_2_{args.direction}_result.json"
    out_json.write_text(json.dumps(out, indent=2))
    out_png = debug_dir / f"m3_2_{args.direction}_overlay.png"
    draw_overlay(crop_png, out_png, kept)

    # ── Summary ────────────────────────────────────────────────────────────────
    print(f"[m3.2] detected {out['total_openings']} openings "
          f"({out['tagged_openings']} tagged, {out['untagged_openings']} untagged, "
          f"{out['needs_review_count']} need review); cost=${totals['cost_usd']:.6f}")
    print(f"[m3.2] M3.1 tags matched to an opening: "
          f"{assigned_tag_centers}/{len(det_tags)}"
          + (f"  MISSED: {[m['tag'] for m in missed_tags]}" if missed_tags else ""))
    print("[per-floor]")
    for fname, s in per_floor.items():
        print(f"   {fname:16} total={s['total']:3}  tagged={s['tagged']:3} "
              f"untagged={s['untagged']:3}  win={s['windows']} door={s['doors']} "
              f"review={s['needs_review']}")
    print(f"[written] {out_json}")
    print(f"[written] {out_png}")


def _png_uri(img: Image.Image) -> str:
    import io
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


if __name__ == "__main__":
    main()
