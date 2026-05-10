"""
Extraction orchestrator (BackgroundTasks entry point).

Flow:
  1. Add extraction-specific ProgressStep rows to the DB.
  2. Branch by detected file type.
  3. Spreadsheet → deterministic parser.
  4. PDF / image → stub extractor (OpenAI path is Phase 5+).
  5. Persist ProjectInfo + WindowItem rows.
  6. Advance session to review_ready.
  7. On failure → set session.status = error + error_message.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session as DBSession

from app.core.database import SessionLocal
from app.models.progress_step import ProgressStep
from app.models.project import ProjectInfo
from app.models.session import Session
from app.models.window_item import WindowItem
from app.services.extraction.spreadsheet_parser import ExtractionResult, parse_spreadsheet
from app.services.extraction.stub_pdf_extractor import extract_stub


# ── Progress step helpers ─────────────────────────────────────────────────────

def _add_step(db: DBSession, session_id: str, name: str, order_index: int) -> ProgressStep:
    step = ProgressStep(
        session_id=session_id,
        name=name,
        status="pending",
        order_index=order_index,
    )
    db.add(step)
    db.flush()
    return step


def _advance(db: DBSession, step: ProgressStep, status: str) -> None:
    step.status = status
    step.updated_at = datetime.now(timezone.utc)
    db.flush()


# ── Persistence helpers ───────────────────────────────────────────────────────

def _save_project_info(
    db: DBSession, session_id: str, info: dict | None
) -> None:
    if not info:
        # Always create a ProjectInfo row so the GET endpoint returns a shape.
        db.add(ProjectInfo(id=str(uuid.uuid4()), session_id=session_id))
    else:
        db.add(
            ProjectInfo(
                id=str(uuid.uuid4()),
                session_id=session_id,
                project_name=info.get("project_name"),
                site_address=info.get("site_address"),
                city=info.get("city"),
                state=info.get("state"),
                zip_code=info.get("zip_code"),
                detected_file_type=info.get("detected_file_type"),
                detected_relevant_pages=info.get("detected_relevant_pages"),
            )
        )
    db.flush()


def _save_window_items(
    db: DBSession, session_id: str, rows: list[dict]
) -> None:
    for row in rows:
        original = {k: v for k, v in row.items() if k not in {"material_type", "confidence"}}
        item = WindowItem(
            id=str(uuid.uuid4()),
            session_id=session_id,
            material_type=row.get("material_type", "Window"),
            tag=row.get("tag"),
            width=row.get("width"),
            height=row.get("height"),
            area=row.get("area"),
            quantity=row.get("quantity"),
            opening_type=row.get("opening_type"),
            material=row.get("material"),
            u_value=row.get("u_value"),
            shgc=row.get("shgc"),
            vt=row.get("vt"),
            glass_type=row.get("glass_type"),
            confidence=row.get("confidence", 0.0),
            notes=row.get("notes"),
            original_extraction=original,
            user_edits={},
        )
        db.add(item)
    db.flush()


# ── Main extraction flow ──────────────────────────────────────────────────────

def _run(
    session_id: str,
    file_path: str,
    file_type: str,
    db: DBSession,
) -> None:
    """Inner extraction; raises on unrecoverable error."""
    session = db.query(Session).filter(Session.id == session_id).first()
    if not session:
        raise RuntimeError(f"Session {session_id} not found.")

    # Close the "Preparing extraction" upload step before adding new ones.
    prep_step = (
        db.query(ProgressStep)
        .filter(ProgressStep.session_id == session_id, ProgressStep.name == "Preparing extraction")
        .first()
    )
    if prep_step:
        _advance(db, prep_step, "completed")
        db.commit()

    # Count existing steps so we can continue the order_index sequence.
    existing = (
        db.query(ProgressStep)
        .filter(ProgressStep.session_id == session_id)
        .count()
    )
    idx = existing  # next order_index

    # ── Choose steps based on file type ──────────────────────────────────
    if file_type == "spreadsheet":
        step_names = [
            "Loading spreadsheet",
            "Detecting columns",
            "Mapping fields",
            "Saving extracted rows",
        ]
    else:
        step_names = [
            "Processing document",
            "Building extraction result",
        ]

    steps: dict[str, ProgressStep] = {}
    for name in step_names:
        steps[name] = _add_step(db, session_id, name, idx)
        idx += 1
    db.commit()

    # ── Read file ─────────────────────────────────────────────────────────
    with open(file_path, "rb") as fh:
        content = fh.read()

    # ── Branch by file type ───────────────────────────────────────────────
    if file_type == "spreadsheet":
        first_step = steps["Loading spreadsheet"]
        _advance(db, first_step, "active")
        db.commit()

        result: ExtractionResult = parse_spreadsheet(content, file_path)

        _advance(db, first_step, "completed")
        _advance(db, steps["Detecting columns"], "completed")
        _advance(db, steps["Mapping fields"], "completed")
        db.commit()

        _advance(db, steps["Saving extracted rows"], "active")
        db.commit()

    else:
        # PDF / image stub path
        first_step = steps["Processing document"]
        _advance(db, first_step, "active")
        db.commit()

        result = extract_stub(file_type)

        _advance(db, first_step, "completed")
        _advance(db, steps["Building extraction result"], "active")
        db.commit()

    # ── Persist results ───────────────────────────────────────────────────
    _save_project_info(db, session_id, result.project_info)
    _save_window_items(db, session_id, result.window_rows)

    # Store warnings on the session's error_message field only if no real error.
    # For warnings (non-fatal), we annotate but do not fail.
    # (Phase 5 will have a dedicated warnings table if needed.)

    # Mark final step completed
    if file_type == "spreadsheet":
        _advance(db, steps["Saving extracted rows"], "completed")
    else:
        _advance(db, steps["Building extraction result"], "completed")

    db.commit()


def run_extraction(session_id: str, file_path: str, file_type: str) -> None:
    """
    Entry point for FastAPI BackgroundTasks.
    Creates its own DB session.
    """
    db = SessionLocal()
    try:
        session = db.query(Session).filter(Session.id == session_id).first()
        if not session:
            return
        try:
            _run(session_id, file_path, file_type, db)
            session = db.query(Session).filter(Session.id == session_id).first()
            if session:
                session.status = "review_ready"
                db.commit()
        except Exception as exc:
            db.rollback()
            session = db.query(Session).filter(Session.id == session_id).first()
            if session:
                session.status = "error"
                session.error_message = str(exc)[:512]
                # Mark any still-active steps as error
                db.query(ProgressStep).filter(
                    ProgressStep.session_id == session_id,
                    ProgressStep.status == "active",
                ).update({"status": "error"})
                db.commit()
    finally:
        db.close()
