"""
Saves uploaded files to storage/uploads/{session_id}/{filename}.
Paths are resolved to the project root so they work regardless of CWD.
"""

from pathlib import Path

from app.core.config import settings

# backend/app/services/file_storage.py → 4 parents up = project root (Xynect/)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent


def _upload_base() -> Path:
    p = Path(settings.upload_dir)
    if not p.is_absolute():
        p = _PROJECT_ROOT / p
    return p


def save_upload(session_id: str, filename: str, content: bytes) -> str:
    """
    Write content to storage/uploads/{session_id}/{safe_filename}.
    Returns the absolute path as a string.
    """
    safe_name = Path(filename).name or "upload"
    dest_dir = _upload_base() / session_id
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / safe_name
    dest.write_bytes(content)
    return str(dest)
