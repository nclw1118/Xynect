#!/usr/bin/env python3
"""
M3.1 prototype — floor segmentation + visible-tag discovery on ONE elevation.

Phase A of the elevation roadmap (see memory: elevation-and-perf-roadmap).
Standalone and decoupled from PDFExtractionService / DB / frontend: it reads
existing debug artifacts and writes a structured result + an overlay for MANUAL
eval. No scoring here — it emits, you judge against your own ground truth.

Hybrid approach (text + vision):
  - Deterministic: pull visible tag tokens (W2/G1/W3/...) and floor/datum labels
    with positions straight from the PDF vector-text layer (precise, no OCR).
  - Vision: gpt-6.1-terra (medium reasoning) uses the elevation crop image + those
    text anchors to produce floor bands and assign each visible tag to a floor.

Outputs (written next to the crop, in the session debug dir):
  m3_1_<direction>_result.json   structured floors + tags + per-floor counts + cost
  m3_1_<direction>_overlay.png   crop with floor-band lines and labeled tag boxes

Usage (from backend/):
  python scripts/m3_1_elevation.py                       # west elevation, defaults
  python scripts/m3_1_elevation.py --direction east --page 10
  python scripts/m3_1_elevation.py --model gpt-6.1-terra --effort medium
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

import fitz  # PyMuPDF
from PIL import Image, ImageDraw, ImageFont
from pydantic import BaseModel, Field

# ── Paths ────────────────────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_ROOT = SCRIPT_DIR.parent          # .../Xynect/backend
PROJECT_ROOT = BACKEND_ROOT.parent        # .../Xynect
sys.path.insert(0, str(BACKEND_ROOT))     # make `app` importable when run from anywhere

from app.services.extraction.pdf.config import PDFExtractionConfig  # noqa: E402
from app.services.extraction.pdf.cost_tracker import CostTracker  # noqa: E402
from app.services.extraction.pdf.llm_client import LangChainLLMClient  # noqa: E402

DEFAULT_SESSION = "329c4b8d-98a5-4635-9c89-d79865900fa8"
TAG_RE = re.compile(r"^(W\d+[A-Z]?|G\d+|D\d+|F\d+|FE\d+|S\d+)$")
FLOOR_RE = re.compile(r"FLOOR|ROOF|CELLAR|BULKHEAD|BASEPLANE", re.IGNORECASE)
ELEV_RE = re.compile(r"^[\(\+\-]?\d+\.\d+'?\)?$")  # e.g. +59.370'  -9.627'  (+34.04')


# ── Structured output schema ─────────────────────────────────────────────────
class FloorBand(BaseModel):
    name: str = Field(description="Floor/datum label, e.g. '7TH_FLOOR', 'ROOF', 'CELLAR'.")
    y_top: float = Field(description="Top edge of the band, normalized 0..1 within the crop (0=top).")
    y_bottom: float = Field(description="Bottom edge of the band, normalized 0..1 within the crop.")
    has_openings: bool = Field(description="Whether this band contains windows/doors (false for roof/bulkhead/cellar).")
    height_above_first_floor_ft: Optional[float] = Field(
        default=None,
        description=(
            "This datum's height in FEET measured from the FIRST FLOOR (1st floor = 0.0; "
            "levels above are positive, cellar/below are negative). Read it from the "
            "elevation value printed at this datum, normalized so the 1st floor is 0. "
            "null if no value is shown for this datum."
        ),
    )


class TagDetection(BaseModel):
    tag: str = Field(description="Visible tag string exactly as shown, e.g. 'W2', 'G1'.")
    bbox: List[float] = Field(description="[x0,y0,x1,y1] normalized 0..1 within the crop.")
    floor: str = Field(description="Name of the FloorBand this tag sits in.")
    confidence: float = 0.0


class M31Response(BaseModel):
    direction: str
    floors: List[FloorBand]
    tags: List[TagDetection]
    notes: str = ""


# ── Deterministic text extraction ────────────────────────────────────────────
def load_region_bbox(regions_path: Path, page_number: int, direction: str) -> List[float]:
    data = json.loads(regions_path.read_text())
    for r in data.get("regions", []):
        if r.get("page_number") == page_number and r.get("direction") == direction:
            # The saved crop PNG is rendered from bbox_expanded.
            return r.get("bbox_expanded") or r.get("bbox_original")
    raise SystemExit(f"No {direction} region on page {page_number} in {regions_path}")


def extract_text_anchors(
    pdf_path: Path, page_index: int, bbox: List[float]
) -> Tuple[List[dict], List[dict], List[dict]]:
    """Return (tags, floor_labels, elevation_values), positions normalized within crop."""
    doc = fitz.open(pdf_path)
    page = doc[page_index]
    W, H = page.rect.width, page.rect.height
    cx0, cy0, cx1, cy1 = bbox[0] * W, bbox[1] * H, bbox[2] * W, bbox[3] * H
    cw, ch = (cx1 - cx0), (cy1 - cy0)

    def norm(x, y):
        return round((x - cx0) / cw, 4), round((y - cy0) / ch, 4)

    tags, floors, elevs = [], [], []
    for x0, y0, x1, y1, word, *_ in page.get_text("words"):
        mx, my = (x0 + x1) / 2, (y0 + y1) / 2
        if not (cx0 <= mx <= cx1 and cy0 <= my <= cy1):
            continue
        nx, ny = norm(mx, my)
        bx0, by0 = norm(x0, y0)
        bx1, by1 = norm(x1, y1)
        if TAG_RE.match(word):
            tags.append({"tag": word, "x": nx, "y": ny, "bbox": [bx0, by0, bx1, by1]})
        elif FLOOR_RE.search(word):
            floors.append({"label": word, "y": ny})
        elif ELEV_RE.match(word):
            elevs.append({"text": word, "value_ft": _elev_value(word), "x": nx, "y": ny})
    doc.close()
    tags.sort(key=lambda t: (t["y"], t["x"]))
    floors.sort(key=lambda f: f["y"])
    elevs.sort(key=lambda e: e["y"])
    return tags, floors, elevs


def _elev_value(word: str) -> Optional[float]:
    m = re.search(r"-?\d+\.\d+", word)
    return float(m.group()) if m else None


def load_catalog(result_path: Path) -> Dict[str, List[str]]:
    d = json.loads(result_path.read_text())
    return {
        "window_tags": sorted({r.get("tag") for r in d.get("extracted_window_rows", []) if r.get("tag")}),
        "door_tags": sorted({r.get("tag") for r in d.get("extracted_door_rows", []) if r.get("tag")}),
    }


# ── Prompt ───────────────────────────────────────────────────────────────────
def build_prompt(direction, scale, tags, floors, elevs, catalog) -> str:
    tag_counts = Counter(t["tag"] for t in tags)
    return f"""
You are an architectural elevation-structure analyst. You are given ONE cropped
building elevation drawing (direction: {direction.upper()}, scale: {scale}) as an
image, plus text already extracted deterministically from the PDF vector layer.

TASK (M3.1 — structure only, do NOT count or infer untagged openings):
1. FLOOR SEGMENTATION: identify each horizontal floor/datum band top-to-bottom.
   Use the dashed datum lines in the image and the floor labels provided below as
   anchors. Return each band's y_top/y_bottom normalized 0..1 within the crop
   (0 = top of image). Mark has_openings=false for roof/bulkhead/cellar/baseplane
   bands that contain no windows or doors.
2. FLOOR HEIGHTS: for each floor band, set height_above_first_floor_ft — the
   datum's vertical height in FEET measured from the FIRST FLOOR. The first floor
   is the 0.0 reference (its printed elevation value reads +0.000'). Levels above
   are positive; cellar/below-grade are negative. Match each floor label to the
   nearest elevation value (closest y) from elevation_values below, and the image,
   to decide the correct number. If a datum shows no elevation value, use null.
3. VISIBLE TAG ASSIGNMENT: for every VISIBLE tag token provided below, return its
   bbox (normalized) and the floor band it sits in. Only use tags that are
   actually visible in the drawing — do NOT invent tags for untagged openings
   (that is a later milestone).

DETERMINISTIC TEXT ANCHORS (from the PDF — trust these for tag text/positions):
floor_labels (label, y): {json.dumps(floors)}
elevation_values (text, value_ft, x, y): {json.dumps(elevs)}
visible_tags (tag, x, y, bbox): {json.dumps(tags)}
visible_tag_counts: {json.dumps(dict(tag_counts))}

SCHEDULE CATALOG (known types this project uses):
window tags: {catalog['window_tags']}
door tags:   {catalog['door_tags']}

Return floors ordered top→bottom and one entry per visible tag.
""".strip()


# ── Overlay drawing ──────────────────────────────────────────────────────────
def _font(size: int):
    try:
        return ImageFont.load_default(size=size)
    except Exception:
        return ImageFont.load_default()


# Distinct colors cycled per floor band.
_PALETTE = [
    (220, 30, 30), (30, 120, 220), (30, 160, 60), (200, 120, 0),
    (150, 40, 200), (0, 150, 150), (200, 0, 120), (90, 90, 90),
]


def draw_overlay(
    crop_png: Path, out_png: Path, floors: List[FloorBand], tags: List[TagDetection]
) -> None:
    im = Image.open(crop_png).convert("RGB")
    W, H = im.size
    draw = ImageDraw.Draw(im, "RGBA")
    lw = max(2, W // 700)
    fsize = max(14, W // 90)
    font = _font(fsize)

    floor_color = {f.name: _PALETTE[i % len(_PALETTE)] for i, f in enumerate(floors)}

    # Floor bands: top/bottom lines + name label.
    for f in floors:
        c = floor_color[f.name]
        yt, yb = f.y_top * H, f.y_bottom * H
        draw.line([(0, yt), (W, yt)], fill=c + (180,), width=lw)
        draw.line([(0, yb), (W, yb)], fill=c + (90,), width=max(1, lw // 2))
        label = f.name
        if f.height_above_first_floor_ft is not None:
            label += f"  [{f.height_above_first_floor_ft:+.3f} ft from 1st]"
        if not f.has_openings:
            label += " (no openings)"
        draw.text((8, yt + 4), label, fill=c, font=font)

    # Tag boxes colored by assigned floor.
    for t in tags:
        c = floor_color.get(t.floor, (255, 0, 0))
        x0, y0, x1, y1 = t.bbox[0] * W, t.bbox[1] * H, t.bbox[2] * W, t.bbox[3] * H
        # pad tiny tag boxes so they are visible
        pad = max(4, W // 300)
        draw.rectangle([x0 - pad, y0 - pad, x1 + pad, y1 + pad], outline=c + (255,), width=lw)
        draw.text((x0 - pad, y1 + pad), t.tag, fill=c, font=_font(max(11, fsize - 4)))

    im.save(out_png)


# ── Main ─────────────────────────────────────────────────────────────────────
def per_floor_counts(floors: List[FloorBand], tags, by_center=True) -> Dict[str, Dict[str, int]]:
    """Count tags per floor. If by_center, assign by y-center into model bands
    (robust); else trust the model's `floor` field."""
    bands = sorted(floors, key=lambda f: f.y_top)

    def band_for(y):
        for f in bands:
            if f.y_top <= y <= f.y_bottom:
                return f.name
        return "UNASSIGNED"

    out: Dict[str, Counter] = {}
    for t in tags:
        if by_center:
            yc = (t["bbox"][1] + t["bbox"][3]) / 2 if isinstance(t, dict) else (t.bbox[1] + t.bbox[3]) / 2
            fname = band_for(yc)
        else:
            fname = t.floor
        tag = t["tag"] if isinstance(t, dict) else t.tag
        out.setdefault(fname, Counter())[tag] += 1
    return {k: dict(v) for k, v in out.items()}


def main() -> None:
    ap = argparse.ArgumentParser(description="M3.1 elevation floor + visible-tag prototype")
    ap.add_argument("--session", default=DEFAULT_SESSION)
    ap.add_argument("--page", type=int, default=10, help="1-based PDF page number")
    ap.add_argument("--direction", default="west")
    ap.add_argument("--model", default="gpt-6.1-terra")
    ap.add_argument("--effort", default="medium")
    args = ap.parse_args()

    debug_dir = BACKEND_ROOT / "storage" / "extraction_debug" / args.session
    pdf_path = PROJECT_ROOT / "storage" / "uploads" / args.session / "TEST PDF.pdf"
    crop_png = debug_dir / f"elevation_page_{args.page:03d}_{args.direction}.png"
    regions_path = debug_dir / "elevation_regions.json"
    result_path = debug_dir / "extraction_result.json"
    for p in (pdf_path, crop_png, regions_path, result_path):
        if not p.exists():
            raise SystemExit(f"Missing input: {p}")

    page_index = args.page - 1
    bbox = load_region_bbox(regions_path, args.page, args.direction)
    tags, floors, elevs = extract_text_anchors(pdf_path, page_index, bbox)
    catalog = load_catalog(result_path)

    # scale from regions.json (per-page)
    scale = ""
    for pg in json.loads(regions_path.read_text()).get("pages", []):
        if pg.get("page_number") == args.page:
            scale = pg.get("scale", "")

    print(f"[deterministic] {len(tags)} visible tags {dict(Counter(t['tag'] for t in tags))}, "
          f"{len(floors)} floor labels, {len(elevs)} elevation values")

    # ── LLM call (reuses the instrumented client → cost tracked) ──────────────
    config = dataclasses.replace(PDFExtractionConfig.from_settings(), llm_model=args.model)
    cost = CostTracker(session_id=args.session, model=args.model)
    client = LangChainLLMClient(config, reasoning_effort=args.effort,
                                stage="m3_1_elevation", cost_tracker=cost)
    structured = client.with_structured_output(M31Response)
    uri = "data:image/png;base64," + base64.b64encode(crop_png.read_bytes()).decode()
    prompt = build_prompt(args.direction, scale, tags, floors, elevs, catalog)
    print(f"[llm] model={args.model} effort={args.effort} ... calling")
    resp: M31Response = client.invoke_multimodal(structured, prompt, [uri],
                                                 label=f"{args.direction}_p{args.page}")

    # ── Assemble + write result ───────────────────────────────────────────────
    totals = cost.to_dict()["totals"]
    out = {
        "session_id": args.session,
        "page": args.page,
        "direction": args.direction,
        "model": args.model,
        "reasoning_effort": args.effort,
        "scale": scale,
        "catalog": catalog,
        "model_floors": [f.model_dump() for f in resp.floors],
        "floor_heights_above_first_floor_ft": {
            f.name: f.height_above_first_floor_ft for f in resp.floors
        },
        "floor_to_floor_heights_ft": _floor_to_floor(resp.floors),
        "model_tags": [t.model_dump() for t in resp.tags],
        "deterministic_elevation_values": elevs,
        "deterministic_tags": tags,
        "deterministic_tag_counts": dict(Counter(t["tag"] for t in tags)),
        "per_floor_counts_deterministic": per_floor_counts(resp.floors, tags, by_center=True),
        "per_floor_counts_model": per_floor_counts(resp.floors, resp.tags, by_center=False),
        "model_notes": resp.notes,
        "llm_cost_usd": totals["cost_usd"],
        "llm_tokens": {k: totals[k] for k in
                       ("input_tokens", "cached_input_tokens", "output_tokens", "reasoning_tokens")},
    }
    out_json = debug_dir / f"m3_1_{args.direction}_result.json"
    out_json.write_text(json.dumps(out, indent=2))

    # Overlay: draw model floor bands + deterministic tag boxes colored by band.
    det_tag_objs = [TagDetection(tag=t["tag"], bbox=t["bbox"],
                                 floor=_assign(resp.floors, t["bbox"]), confidence=1.0)
                    for t in tags]
    out_png = debug_dir / f"m3_1_{args.direction}_overlay.png"
    draw_overlay(crop_png, out_png, resp.floors, det_tag_objs)

    # ── Summary ───────────────────────────────────────────────────────────────
    print(f"[llm] {len(resp.floors)} floors, {len(resp.tags)} tags assigned; "
          f"cost=${totals['cost_usd']:.6f} "
          f"(in={totals['input_tokens']}, out={totals['output_tokens']})")
    print("[floor heights above 1st floor (ft)]")
    for f in sorted(resp.floors, key=lambda f: (f.height_above_first_floor_ft is None,
                                                -(f.height_above_first_floor_ft or 0))):
        print(f"   {f.name:18} {f.height_above_first_floor_ft}")
    print("[per-floor counts, deterministic tags → model bands]")
    for fname, counts in out["per_floor_counts_deterministic"].items():
        print(f"   {fname:16} {counts}")
    print(f"[written] {out_json}")
    print(f"[written] {out_png}")


def _floor_to_floor(floors: List[FloorBand]) -> Dict[str, float]:
    """Height from each level to the next one up, derived from the per-floor
    heights (ordered by elevation). E.g. {'1st_FLOOR->2ND_FLOOR': 9.37, ...}."""
    leveled = [(f.name, f.height_above_first_floor_ft) for f in floors
               if f.height_above_first_floor_ft is not None]
    leveled.sort(key=lambda x: x[1])
    out: Dict[str, float] = {}
    for (n0, h0), (n1, h1) in zip(leveled, leveled[1:]):
        out[f"{n0}->{n1}"] = round(h1 - h0, 3)
    return out


def _assign(floors: List[FloorBand], bbox: List[float]) -> str:
    yc = (bbox[1] + bbox[3]) / 2
    for f in sorted(floors, key=lambda f: f.y_top):
        if f.y_top <= yc <= f.y_bottom:
            return f.name
    return "UNASSIGNED"


if __name__ == "__main__":
    main()
