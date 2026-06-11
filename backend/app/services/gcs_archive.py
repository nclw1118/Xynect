"""
Stage 5A — hybrid local + GCS archival.

WHAT THIS IS (and is not):
  - Local disk is STILL the working copy. Uploads are saved locally and the
    extraction pipeline reads/writes local paths exactly as before.
  - GCS is used here only as a durable, post-extraction COPY of artifacts.
    It is NOT the source of truth and is NOT consulted during extraction.

GUARANTEES:
  - Nothing in this module runs during the initial upload request or inside
    the critical extraction path (LLM calls, rendering, page classification,
    DB row saving). It is invoked only AFTER extraction has completed and
    results are already persisted.
  - Every public function is best-effort: failures are logged as warnings and
    swallowed. They must never raise into the extraction flow or change the
    session's success/failure status.

No queues / Celery / Pub/Sub / Cloud Tasks are introduced at this stage —
archival simply runs at the tail of the existing BackgroundTask.
"""

from __future__ import annotations

import logging
from pathlib import Path

from app.core.config import settings

logger = logging.getLogger(__name__)

# backend/app/services/gcs_archive.py → 4 parents up = project root (Xynect/)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent


def _resolve_local_dir(raw_path: str) -> Path:
    """
    Resolve a possibly-relative configured path to an absolute one.

    The debug dir default ("./storage/extraction_debug") is relative; depending
    on the process CWD it may resolve against either the project root or the
    backend/ dir. Prefer whichever actually exists so archival finds the files.
    """
    p = Path(raw_path)
    if p.is_absolute():
        return p
    root_relative = _PROJECT_ROOT / p
    if root_relative.exists():
        return root_relative
    cwd_relative = Path.cwd() / p
    if cwd_relative.exists():
        return cwd_relative
    # Neither exists yet; return the project-root candidate for a clean log.
    return root_relative


def _bucket():
    """
    Lazily build a GCS bucket handle. Imported here (not at module top) so the
    google-cloud-storage dependency is only required when archival is enabled.
    Returns None if GCS is not configured/available.
    """
    if not settings.gcs_bucket_name:
        logger.warning("GCS archival enabled but GCS_BUCKET_NAME is empty; skipping.")
        return None
    try:
        from google.cloud import storage  # noqa: PLC0415 — intentional lazy import
    except ImportError:
        logger.warning("google-cloud-storage not installed; skipping GCS archival.")
        return None
    try:
        # Uses Application Default Credentials (ADC). On Cloud Run / GCE this is
        # the attached service account; locally it is `gcloud auth` credentials.
        client = storage.Client()
        return client.bucket(settings.gcs_bucket_name)
    except Exception as exc:  # noqa: BLE001 — best-effort, never propagate
        logger.warning("Could not init GCS client/bucket: %s", exc)
        return None


def archive_uploaded_file(session_id: str, local_file_path: str) -> None:
    """
    Upload a copy of the original uploaded file to
    gs://<bucket>/<GCS_UPLOAD_PREFIX>/<session_id>/<filename>.

    Best-effort: logs a warning and returns on any failure.
    """
    bucket = _bucket()
    if bucket is None:
        return

    src = Path(local_file_path)
    if not src.is_file():
        logger.warning("Upload archive skipped; local file missing: %s", local_file_path)
        return

    blob_name = f"{settings.gcs_upload_prefix}/{session_id}/{src.name}"
    try:
        bucket.blob(blob_name).upload_from_filename(str(src))
        logger.info("Archived upload to gs://%s/%s", settings.gcs_bucket_name, blob_name)
    except Exception as exc:  # noqa: BLE001 — best-effort
        logger.warning("Failed to archive upload %s to GCS: %s", blob_name, exc)


def archive_debug_dir(session_id: str, local_debug_dir: str | Path) -> None:
    """
    Upload the local extraction debug directory (if it exists) to
    gs://<bucket>/<GCS_DEBUG_PREFIX>/<session_id>/... preserving relative paths.

    Best-effort: logs a warning and returns on any failure. A missing debug dir
    is normal (e.g. spreadsheet extraction writes none) and is not an error.
    """
    debug_dir = Path(local_debug_dir)
    if not debug_dir.is_dir():
        logger.info("No debug dir to archive for session %s (%s)", session_id, debug_dir)
        return

    bucket = _bucket()
    if bucket is None:
        return

    uploaded = 0
    for file_path in sorted(debug_dir.rglob("*")):
        if not file_path.is_file():
            continue
        rel = file_path.relative_to(debug_dir)
        blob_name = f"{settings.gcs_debug_prefix}/{session_id}/{rel.as_posix()}"
        try:
            bucket.blob(blob_name).upload_from_filename(str(file_path))
            uploaded += 1
        except Exception as exc:  # noqa: BLE001 — best-effort, keep going
            logger.warning("Failed to archive debug file %s to GCS: %s", blob_name, exc)

    if uploaded:
        logger.info(
            "Archived %d debug file(s) to gs://%s/%s/%s/",
            uploaded, settings.gcs_bucket_name, settings.gcs_debug_prefix, session_id,
        )


def archive_session_artifacts(session_id: str, uploaded_file_path: str) -> None:
    """
    Post-extraction entry point. Archives the original upload and the per-session
    extraction debug directory to GCS.

    Call this only AFTER extraction has finished and results are saved. Fully
    guarded: any failure is logged and swallowed so extraction outcome is never
    affected.
    """
    if not settings.gcs_enabled or not settings.gcs_upload_after_extraction:
        return

    try:
        archive_uploaded_file(session_id, uploaded_file_path)
        debug_dir = _resolve_local_dir(settings.pdf_debug_output_dir) / session_id
        archive_debug_dir(session_id, debug_dir)
    except Exception as exc:  # noqa: BLE001 — final safety net
        logger.warning("GCS archival failed for session %s: %s", session_id, exc)
