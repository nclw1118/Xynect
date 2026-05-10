import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session as DBSession

from app.core.config import settings
from app.core.database import get_db
from app.models.progress_step import ProgressStep
from app.models.session import Session
from app.schemas.session import ProgressResponse, ProgressStepSchema, UploadResponse
from app.services.extraction.extraction_agent import run_extraction
from app.services.file_detection import classify_file, validate_extension, validate_magic_bytes
from app.services.file_storage import save_upload

router = APIRouter(prefix="/api/sessions", tags=["sessions"])

_UPLOAD_STEPS = [
    "Uploading file",
    "Detecting file type",
    "Saving file",
    "Preparing extraction",
]


def _create_steps(db: DBSession, session_id: str) -> list[ProgressStep]:
    steps = [
        ProgressStep(
            session_id=session_id,
            name=name,
            status="pending",
            order_index=i,
        )
        for i, name in enumerate(_UPLOAD_STEPS)
    ]
    db.add_all(steps)
    return steps


def _mark(steps: list[ProgressStep], name: str, status: str) -> None:
    for s in steps:
        if s.name == name:
            s.status = status
            s.updated_at = datetime.now(timezone.utc)
            return


@router.post("/upload", response_model=UploadResponse)
async def upload_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: DBSession = Depends(get_db),
) -> UploadResponse:
    content = await file.read()

    max_bytes = settings.max_upload_mb * 1024 * 1024
    if len(content) > max_bytes:
        size_mb = len(content) / 1024 / 1024
        raise HTTPException(
            status_code=413,
            detail=f"File too large ({size_mb:.1f} MB). Maximum allowed is {settings.max_upload_mb} MB.",
        )

    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    filename = file.filename or "upload"

    try:
        ext = validate_extension(filename)
        validate_magic_bytes(content, ext)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    detected_type = classify_file(content, ext)
    session_id = str(uuid.uuid4())

    session = Session(
        id=session_id,
        status="processing",
        uploaded_file_name=filename,
        uploaded_file_type=detected_type,
    )
    db.add(session)

    steps = _create_steps(db, session_id)
    _mark(steps, "Uploading file", "completed")
    _mark(steps, "Detecting file type", "completed")

    saved_path = save_upload(session_id, filename, content)
    session.uploaded_file_path = saved_path
    _mark(steps, "Saving file", "completed")
    _mark(steps, "Preparing extraction", "active")

    db.commit()

    background_tasks.add_task(run_extraction, session_id, saved_path, detected_type)

    return UploadResponse(
        session_id=session_id,
        status="processing",
        message="File uploaded successfully. Extraction started.",
    )


@router.get("/{session_id}/progress", response_model=ProgressResponse)
def get_progress(session_id: str, db: DBSession = Depends(get_db)) -> ProgressResponse:
    session = db.query(Session).filter(Session.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")

    steps = (
        db.query(ProgressStep)
        .filter(ProgressStep.session_id == session_id)
        .order_by(ProgressStep.order_index)
        .all()
    )

    current_step: str | None = next(
        (s.name for s in steps if s.status == "active"),
        next((s.name for s in reversed(steps) if s.status == "completed"), None),
    )

    return ProgressResponse(
        session_id=session_id,
        status=session.status,
        current_step=current_step,
        steps=[ProgressStepSchema(name=s.name, status=s.status) for s in steps],
    )
