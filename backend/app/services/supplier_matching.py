"""
Deterministic supplier matching and pricing.

Scoring (100 pts total):
  State match          25
  Material type match  15  (always "Window" → always awarded when supplier supports it)
  Opening type match   15
  Window material      15
  Size range           15
  Glass type            5
  Lead time advantage   5
  Reliability           5

Missing fields: skip that component's points, emit a risk note, do not fail.
"""

import re
import uuid
from dataclasses import dataclass, field

from app.models.supplier import Supplier
from app.models.window_item import WindowItem


# ── Dimension helpers ──────────────────────────────────────────────────────────

def _to_inches(s: str | None) -> float | None:
    """Parse a dimension string like '3 ft', '36 in', '2.5' → float inches."""
    if not s:
        return None
    s = s.strip().lower()
    m = re.match(r"([\d.]+)\s*(ft|feet|in|inch|inches|\")?", s)
    if not m:
        return None
    value = float(m.group(1))
    unit = (m.group(2) or "").strip()
    if unit in ("ft", "feet"):
        return value * 12.0
    return value   # default: treat as inches


def _area_sf(width_in: float | None, height_in: float | None) -> float | None:
    if width_in is None or height_in is None:
        return None
    return (width_in / 12.0) * (height_in / 12.0)


# ── Pricing factors ────────────────────────────────────────────────────────────

_OPENING_FACTOR: dict[str, float] = {
    "casement": 1.10,
    "double-hung": 1.05,
    "single-hung": 1.00,
    "fixed": 0.95,
    "picture": 0.88,
    "sliding": 0.90,
    "awning": 1.10,
    "jalousie": 1.00,
}

_MATERIAL_FACTOR: dict[str, float] = {
    "aluminum": 1.00,
    "steel": 1.15,
    "vinyl": 0.85,
    "fiberglass": 0.90,
    "wood": 1.20,
    "metal": 1.00,
}

# Reference area for size_factor normalisation (15 sf ≈ a 3×5 ft window)
_REFERENCE_AREA_SF = 15.0

# Lead-time range across all seeded suppliers (days)
_LEAD_MIN = 10
_LEAD_MAX = 25


# ── Result type ────────────────────────────────────────────────────────────────

@dataclass
class MatchResult:
    supplier: Supplier
    tag: str
    unit_price: float
    quantity: int
    estimated_total: float
    match_score: float        # 0.0–1.0
    match_reason: str
    risk_notes: str
    recommendation_id: str = field(default_factory=lambda: str(uuid.uuid4()))


# ── Core matching ──────────────────────────────────────────────────────────────

def _score(
    item: WindowItem,
    supplier: Supplier,
    width_in: float | None,
    height_in: float | None,
) -> tuple[float, list[str], list[str]]:
    """
    Return (raw_score_0_to_100, reason_parts, risk_parts).
    """
    score = 0.0
    reasons: list[str] = []
    risks: list[str] = []

    state = (item.opening_type or "").strip()  # re-use field name; actual value below
    state = None  # re-declare cleanly
    # Pull state from project info — passed implicitly via session.  For the
    # scorer we receive it as part of window_item through a helper call below.
    # See match_window() which extracts state and passes it in.

    return score, reasons, risks   # placeholder — see match_window


def match_window(
    item: WindowItem,
    suppliers: list[Supplier],
    state: str | None,
    top_n: int = 3,
) -> list[MatchResult]:
    """
    Score every supplier against one WindowItem, return top_n sorted results.
    """
    width_in = _to_inches(item.width)
    height_in = _to_inches(item.height)
    area_sf = _area_sf(width_in, height_in)

    results: list[MatchResult] = []

    for supplier in suppliers:
        score = 0.0
        reasons: list[str] = []
        risks: list[str] = []

        # ── 1. State match (25 pts) ───────────────────────────────────────
        if not state:
            risks.append("State missing; regional match based on general availability.")
        elif state.upper() in [s.upper() for s in (supplier.supported_states or [])]:
            score += 25.0
            reasons.append(f"serves {state}")
        else:
            pass  # no points

        # ── 2. Material type match (15 pts) ──────────────────────────────
        mat_type = (item.material_type or "Window").strip()
        if mat_type in (supplier.supported_material_types or []):
            score += 15.0
        # material_type is always "Window" and all suppliers support it → always awarded

        # ── 3. Opening type match (15 pts) ───────────────────────────────
        opening = (item.opening_type or "").strip()
        if not opening:
            risks.append("Opening type missing; verify supplier compatibility.")
        else:
            sup_openings = [o.lower() for o in (supplier.supported_opening_types or [])]
            if opening.lower() in sup_openings:
                score += 15.0
                reasons.append(f"supports {opening}")
            # else 0 pts — no reason, no extra risk

        # ── 4. Window material match (15 pts) ────────────────────────────
        material = (item.material or "").strip()
        if not material:
            risks.append("Frame material missing; verify supplier compatibility.")
        else:
            sup_mats = [m.lower() for m in (supplier.supported_window_materials or [])]
            if material.lower() in sup_mats:
                score += 15.0
                reasons.append(f"{material} frame supported")

        # ── 5. Size range match (15 pts) ─────────────────────────────────
        if width_in is None or height_in is None:
            risks.append("Dimensions missing; unit price is an approximate base price.")
        else:
            w_ok = (
                (supplier.min_width is None or width_in >= supplier.min_width)
                and (supplier.max_width is None or width_in <= supplier.max_width)
            )
            h_ok = (
                (supplier.min_height is None or height_in >= supplier.min_height)
                and (supplier.max_height is None or height_in <= supplier.max_height)
            )
            if w_ok and h_ok:
                score += 15.0
                reasons.append("size in range")
            elif w_ok or h_ok:
                score += 7.0  # partial credit

        # ── 6. Glass type match (5 pts) ───────────────────────────────────
        glass = (item.glass_type or "").strip()
        if not glass:
            risks.append("Glass type missing; verify glazing requirements before ordering.")
        else:
            sup_glass = [g.lower() for g in (supplier.supported_glass_types or [])]
            if glass.lower() in sup_glass:
                score += 5.0

        # ── 7. Lead time advantage (5 pts) ────────────────────────────────
        lead_range = _LEAD_MAX - _LEAD_MIN
        if lead_range > 0:
            score += 5.0 * (_LEAD_MAX - supplier.lead_time_days) / lead_range
        else:
            score += 2.5

        # ── 8. Reliability (5 pts) ────────────────────────────────────────
        score += (supplier.reliability_score or 0.0) * 5.0

        # ── NFRC risk notes ───────────────────────────────────────────────
        if not item.u_value:
            risks.append("U-Value missing; verify compliance before order.")
        if not item.shgc:
            risks.append("SHGC missing; verify solar performance requirements.")

        # ── Pricing ───────────────────────────────────────────────────────
        size_factor = 1.0
        if area_sf is not None:
            size_factor = max(0.5, min(3.0, (area_sf / _REFERENCE_AREA_SF) ** 0.5))

        opening_factor = _OPENING_FACTOR.get((opening or "").lower(), 1.0)
        material_factor = _MATERIAL_FACTOR.get((material or "").lower(), 1.0)

        unit_price = round(
            supplier.base_unit_price * size_factor * opening_factor * material_factor, 2
        )

        # Quantity
        raw_qty = (item.quantity or "").strip()
        if raw_qty:
            try:
                qty = int(float(raw_qty))
            except ValueError:
                qty = 1
                risks.append("Quantity value unreadable; total uses quantity = 1 as placeholder.")
        else:
            qty = 1
            risks.append("Quantity missing; total price uses quantity = 1 as placeholder.")

        estimated_total = round(unit_price * qty, 2)

        # ── Assemble result ───────────────────────────────────────────────
        reason_str = (
            f"Matches on: {', '.join(reasons)}." if reasons else "General availability match."
        )
        risk_str = " ".join(risks) if risks else ""
        match_score_pct = round(min(score, 100.0) / 100.0, 3)

        results.append(
            MatchResult(
                supplier=supplier,
                tag=item.tag or "?",
                unit_price=unit_price,
                quantity=qty,
                estimated_total=estimated_total,
                match_score=match_score_pct,
                match_reason=reason_str,
                risk_notes=risk_str,
            )
        )

    results.sort(key=lambda r: r.match_score, reverse=True)
    return results[:top_n]


def match_all(
    window_items: list[WindowItem],
    suppliers: list[Supplier],
    state: str | None,
    top_n: int = 3,
) -> dict[str, list[MatchResult]]:
    """Return {tag: [MatchResult, ...]} for all window items."""
    out: dict[str, list[MatchResult]] = {}
    for item in window_items:
        tag = item.tag or f"item_{item.id[:6]}"
        out[tag] = match_window(item, suppliers, state, top_n=top_n)
    return out
