"""
Value normalization helpers.

Rules:
- Store all values as strings (consistent with WindowItem schema).
- Append units when the column header implies them (ft, sf).
- Never invent values — return empty string if value is blank/unparseable.
- Do not round or alter numeric values beyond stripping whitespace.
"""

import re


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
