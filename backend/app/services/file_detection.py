"""
Extension and magic-byte validation, file-type classification.

Classification output values:
  multi_page_pdf   — PDF with more than one page
  single_page_pdf  — PDF with exactly one page
  image            — JPEG or PNG
  spreadsheet      — XLSX, XLS, or CSV
"""

import io

import fitz  # PyMuPDF

ALLOWED_EXTENSIONS = frozenset({".pdf", ".jpg", ".jpeg", ".png", ".xlsx", ".xls", ".csv"})

# Magic bytes keyed by lowercase extension.
# CSV has no magic bytes — extension-only check is used.
_MAGIC: dict[str, bytes] = {
    ".pdf": b"%PDF",
    ".jpg": b"\xFF\xD8\xFF",
    ".jpeg": b"\xFF\xD8\xFF",
    ".png": b"\x89PNG\r\n\x1a\n",
    ".xlsx": b"PK\x03\x04",          # ZIP-based (Office Open XML)
    ".xls": b"\xD0\xCF\x11\xE0",    # Compound Document Binary Format
}


def get_extension(filename: str) -> str:
    """Return lowercase extension including leading dot, e.g. '.pdf'. Empty string if none."""
    parts = filename.rsplit(".", 1)
    return ("." + parts[1].lower()) if len(parts) == 2 else ""


def validate_extension(filename: str) -> str:
    """Return the extension or raise ValueError for unsupported types."""
    ext = get_extension(filename)
    if ext not in ALLOWED_EXTENSIONS:
        human_list = ", ".join(sorted(ALLOWED_EXTENSIONS))
        raise ValueError(
            f"Unsupported file type '{ext or '(none)'}'. Accepted types: {human_list}."
        )
    return ext


def validate_magic_bytes(content: bytes, ext: str) -> None:
    """Raise ValueError if the file's magic bytes do not match its extension."""
    expected = _MAGIC.get(ext)
    if expected is None:
        return  # CSV — no magic bytes to check
    if not content.startswith(expected):
        raise ValueError(
            f"File content does not match the expected format for {ext}. "
            "The file may be corrupted or mislabeled."
        )


def classify_file(content: bytes, ext: str) -> str:
    """Return one of: multi_page_pdf, single_page_pdf, image, spreadsheet."""
    if ext in {".jpg", ".jpeg", ".png"}:
        return "image"
    if ext in {".xlsx", ".xls", ".csv"}:
        return "spreadsheet"
    if ext == ".pdf":
        try:
            doc = fitz.open(stream=io.BytesIO(content), filetype="pdf")
            page_count = len(doc)
            doc.close()
            return "multi_page_pdf" if page_count > 1 else "single_page_pdf"
        except Exception:
            return "single_page_pdf"
    return "spreadsheet"
