"""
Value normalization helpers.

Rules:
- Store all values as strings (consistent with WindowItem schema).
- Append units when the column header implies them (ft, sf).
- Never invent values — return empty string if value is blank/unparseable.
- Do not round or alter numeric values beyond stripping whitespace.

Area calculation helpers (parse_dimension_to_feet, calculate_area) are used
by the extraction agent to fill area deterministically after LLM extraction.
They must NOT be called for Excel/CSV rows that already have an explicit area
from the AREA(SF) column.
"""

import re


# ── Dimension parsing ──────────────────────────────────────────────────────────

def parse_dimension_to_feet(value: str | None) -> float | None:
    """
    Parse a dimension string to a float in feet.

    Handles:
      "3 ft" / "3 feet" / "3'"       → 3.0
      "36 in" / "36 inches" / "36\""  → 3.0
      "3'-6\"" / "3'6\""              → 3.5
      "3.5" (no unit)                 → None  (ambiguous — refuse to guess)
      "915 mm"                        → None  (mm not supported in MVP)

    Returns None when units are absent or ambiguous so we never silently
    assume the wrong unit.
    """
    if not value:
        return None
    v = value.strip().lower()

    # feet-inches compound: 3'-6", 3'6", 3' 6"
    m = re.match(r"(\d+)\s*'\s*-?\s*(\d+(?:\.\d+)?)\s*\"?", v)
    if m:
        return float(m.group(1)) + float(m.group(2)) / 12.0

    # feet only: 3 ft, 3 feet, 3'
    m = re.match(r"(\d+(?:\.\d+)?)\s*(?:ft|feet|')\b", v)
    if m:
        return float(m.group(1))

    # inches only: 36 in, 36 inches, 36"
    m = re.match(r"(\d+(?:\.\d+)?)\s*(?:in|inch|inches|\")\b", v)
    if m:
        return float(m.group(1)) / 12.0

    # No recognised unit → refuse to assume
    return None


def calculate_area(width: str | None, height: str | None) -> str | None:
    """
    Calculate area in square feet from two dimension strings.

    Returns a formatted string like "15.0 sf", or None when:
    - either dimension is missing
    - either dimension has no recognised unit
    - units are mixed or ambiguous

    Never invented, never guessed.
    """
    w_ft = parse_dimension_to_feet(width)
    h_ft = parse_dimension_to_feet(height)
    if w_ft is None or h_ft is None:
        return None
    area_sf = w_ft * h_ft
    # Format: drop trailing zero if it's a whole number
    if area_sf == int(area_sf):
        return f"{int(area_sf)} sf"
    return f"{area_sf:.2f} sf"


def _strip_to_numeric(raw: str) -> str:
    """Strip everything except digits and decimal point."""
    cleaned = re.sub(r"[^\d.]", "", raw.strip())
    return cleaned


def normalize_value(field: str, raw: str, unit: str | None) -> str:
    """
    Normalize a raw cell value for a given canonical field.

    Returns a clean string to store in the WindowItem, or empty string
    if the value is blank or cannot be meaningfully normalized.
    """
    v = raw.strip()
    if not v:
        return ""

    if field in {"width", "height"}:
        numeric = _strip_to_numeric(v)
        if not numeric:
            return v  # keep original if non-numeric (e.g., "36 in" already)
        if unit:
            return f"{numeric} {unit}"
        return numeric

    if field == "area":
        numeric = _strip_to_numeric(v)
        if not numeric:
            return v
        if unit:
            return f"{numeric} {unit}"
        return numeric

    if field == "quantity":
        # Quantities should be whole numbers; strip decimals and non-digits.
        numeric = _strip_to_numeric(v)
        if not numeric:
            return v
        # If it looks like a float (e.g. "2.0"), convert to int string.
        try:
            return str(int(float(numeric)))
        except ValueError:
            return numeric

    if field in {"u_value", "shgc", "vt"}:
        # NFRC values: keep as-is numeric string.
        numeric = _strip_to_numeric(v)
        return numeric if numeric else v

    # All other fields (tag, opening_type, material, glass_type, notes, etc.):
    # return stripped as-is.
    return v
