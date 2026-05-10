"""
Deterministic column header normalization and alias-based field mapping.

Priority:
  1. Exact normalized match against alias set
  2. Substring containment (alias wholly contained in header, or vice versa) — only when unambiguous
  3. No match → column ignored, warning emitted

If the same canonical field is matched by two different source columns,
the first match wins and a warning is emitted for the duplicate.
"""

import re
from dataclasses import dataclass


@dataclass
class ColumnMapping:
    field: str          # canonical WindowItem field name
    unit: str | None    # "ft", "sf", or None
    confidence: float   # 0.95 for exact, 0.80 for substring
    method: str         # "exact" | "substring"
    source_header: str  # original header text


# Alias sets keyed by canonical field name.
# All aliases are already in normalized form (see _normalize below).
_ALIASES: dict[str, set[str]] = {
    "tag": {
        "tag", "window tag", "wintag", "win tag", "mark", "label",
        "window id", "win id", "window no", "win no",
    },
    "opening_type": {
        "type", "opening type", "window type", "style",
        "operation", "op type", "open type",
    },
    "quantity": {
        "qty", "quantity", "count", "num", "number",
        "no", "quant", "units", "pieces", "pcs",
    },
    "width": {
        "width", "width ft", "window width", "w",
        "wid", "w ft", "width in", "w in",
    },
    "height": {
        "height", "height ft", "length", "length ft",
        "window height", "h", "ht", "len", "h ft",
        "height in", "h in", "length in",
    },
    "area": {
        "area", "area sf", "area sq ft", "square feet",
        "sq ft", "sqft", "sf",
    },
    "material": {
        "material", "frame material", "mat", "frame",
        "framing", "window material", "frame mat",
    },
    "u_value": {
        "u value", "u factor", "ufactor", "uvalue",
        "u val", "thermal transmittance",
    },
    "shgc": {
        "shgc", "solar heat gain", "solar heat gain coefficient",
        "shg", "solar gain",
    },
    "vt": {
        "vt", "visible transmittance", "visible trans",
        "vlt", "vis trans", "visual transmittance",
    },
    "glass_type": {
        "glass type", "glass", "glazing", "glazing type",
        "glaz", "glass spec",
    },
    "notes": {
        "notes", "note", "comments", "comment",
        "remarks", "description", "desc",
    },
}

# Unit embedded in the header for width/height → append "ft" to values.
# Similarly for area → "sf".
_UNIT_SIGNALS: dict[str, str] = {
    " ft": "ft",
    "(ft)": "ft",
    "_ft": "ft",
    " in": "in",
    "(in)": "in",
    "_in": "in",
    " sf": "sf",
    "(sf)": "sf",
    "_sf": "sf",
    "sq ft": "sf",
    "sqft": "sf",
    "square feet": "sf",
}


def _normalize(h: str) -> str:
    """
    Lowercase, strip parenthetical unit hints, collapse punctuation to spaces.
    Returns a stable key for alias lookup.
    """
    h = h.lower().strip()
    # Remove parenthetical content: (ft), (sf), (in), etc.
    h = re.sub(r"\([^)]*\)", " ", h)
    # Replace underscores and dashes with spaces
    h = re.sub(r"[_\-]+", " ", h)
    # Drop everything that isn't alphanumeric or space
    h = re.sub(r"[^a-z0-9 ]+", " ", h)
    # Collapse whitespace
    return re.sub(r"\s+", " ", h).strip()


def _detect_unit(raw_header: str) -> str | None:
    """Infer a unit from the raw header text before normalization."""
    low = raw_header.lower()
    for signal, unit in _UNIT_SIGNALS.items():
        if signal in low:
            return unit
    return None


def _find_field(normalized_header: str) -> tuple[str, str] | None:
    """
    Return (field, method) if a canonical field is found, else None.
    method is "exact" or "substring".
    """
    # Pass 1: exact match
    for field, aliases in _ALIASES.items():
        if normalized_header in aliases:
            return field, "exact"

    # Pass 2: substring containment — alias wholly contained in header
    # Only if it's a meaningful alias (len >= 2 chars) to avoid false positives.
    matches = []
    for field, aliases in _ALIASES.items():
        for alias in aliases:
            if len(alias) >= 3 and alias in normalized_header:
                matches.append((field, "substring"))
                break
            if len(alias) >= 3 and normalized_header in alias:
                matches.append((field, "substring"))
                break

    if len(matches) == 1:
        return matches[0]
    # Multiple substring matches → ambiguous → do not guess
    return None


def map_headers(
    headers: list[str],
) -> tuple[dict[str, ColumnMapping], list[str]]:
    """
    Map a list of source headers to canonical field names.

    Returns:
        mappings: {source_header: ColumnMapping}
        warnings: list of warning strings
    """
    mappings: dict[str, ColumnMapping] = {}
    warnings: list[str] = []
    claimed_fields: dict[str, str] = {}  # field → first source_header that claimed it

    for raw_header in headers:
        raw_header_stripped = str(raw_header).strip()
        if not raw_header_stripped:
            continue

        normalized = _normalize(raw_header_stripped)
        unit = _detect_unit(raw_header_stripped)

        result = _find_field(normalized)
        if result is None:
            warnings.append(
                f"Column '{raw_header_stripped}' could not be mapped to a known field and will be ignored."
            )
            continue

        field, method = result
        confidence = 0.95 if method == "exact" else 0.80

        if field in claimed_fields:
            warnings.append(
                f"Column '{raw_header_stripped}' maps to '{field}' but that field is already mapped "
                f"from '{claimed_fields[field]}'. Ignoring duplicate."
            )
            continue

        claimed_fields[field] = raw_header_stripped
        mappings[raw_header_stripped] = ColumnMapping(
            field=field,
            unit=unit,
            confidence=confidence,
            method=method,
            source_header=raw_header_stripped,
        )

    return mappings, warnings
