"""
Extraction orchestrator (BackgroundTasks entry point).

Flow:
  1. Close the "Preparing extraction" upload step.
  2. Branch by detected file type:
     - spreadsheet  → deterministic parser (no LLM)
     - pdf / image  → LLM provider (stub or OpenAI based on settings)
  3. Persist ProjectInfo + WindowItem rows.
  4. Advance session to review_ready.
  5. On failure → session.status = error + error_message.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session as DBSession

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.progress_step import ProgressStep
from app.models.project import ProjectInfo
from app.models.session import Session
from app.models.window_item import WindowItem
from app.services.extraction.normalizers import calculate_area
from app.services.extraction.spreadsheet_parser import ExtractionResult, parse_spreadsheet


# ── Progress helpers ──────────────────────────────────────────────────────────

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

def _save_project_info(db: DBSession, session_id: str, info: dict | None) -> None:
    if not info:
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


def _save_window_items(db: DBSession, session_id: str, rows: list[dict]) -> None:
    for row in rows:
        original = {k: v for k, v in row.items() if k not in {"material_type", "confidence"}}
        db.add(
            WindowItem(
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
        )
    db.flush()


# ── Spreadsheet extraction branch ─────────────────────────────────────────────

def _run_spreadsheet(
    session_id: str,
    content: bytes,
    file_path: str,
    db: DBSession,
    base_idx: int,
) -> ExtractionResult:
    step_names = ["Loading spreadsheet", "Detecting columns", "Mapping fields", "Saving extracted rows"]
    steps = {n: _add_step(db, session_id, n, base_idx + i) for i, n in enumerate(step_names)}
    db.commit()

    _advance(db, steps["Loading spreadsheet"], "active"); db.commit()
    result = parse_spreadsheet(content, file_path)
    _advance(db, steps["Loading spreadsheet"], "completed")
    _advance(db, steps["Detecting columns"], "completed")
    _advance(db, steps["Mapping fields"], "completed")
    _advance(db, steps["Saving extracted rows"], "active")
    db.commit()

    return result


# ── PDF + OpenAI branch (LangChain crop-planning algorithm) ──────────────────

def _run_pdf_langchain(
    session_id: str,
    content: bytes,
    file_type: str,
    db: DBSession,
    base_idx: int,
) -> ExtractionResult:
    from app.services.extraction.pdf.config import PDFExtractionConfig
    from app.services.extraction.pdf.service import (
        PDFExtractionService,
        STEP_NAMES_IN_ORDER,
    )
    from app.services.extraction.progress_reporter import ProgressReporter

    reporter = ProgressReporter(db, session_id, STEP_NAMES_IN_ORDER, base_idx)
    config = PDFExtractionConfig.from_settings()
    service = PDFExtractionService(config)
    return service.run(content, file_type, session_id, reporter)


# ── LLM extraction branch (PDF / image) ──────────────────────────────────────

def _run_llm(
    session_id: str,
    content: bytes,
    file_type: str,
    db: DBSession,
    base_idx: int,
) -> ExtractionResult:
    from app.services.llm.factory import get_provider

    provider = get_provider()
    is_multi = file_type == "multi_page_pdf"

    if is_multi:
        step_names = [
            "Rendering document pages",
            "Classifying document pages",
            "Extracting project information",
            "Extracting window schedule",
            "Normalizing extracted data",
            "Saving extracted rows",
        ]
    else:
        step_names = [
            "Rendering document",
            "Extracting window schedule",
            "Normalizing extracted data",
            "Saving extracted rows",
        ]

    steps = {n: _add_step(db, session_id, n, base_idx + i) for i, n in enumerate(step_names)}
    db.commit()

    # ── Render ─────────────────────────────────────────────────────────────
    render_key = "Rendering document pages" if is_multi else "Rendering document"
    _advance(db, steps[render_key], "active"); db.commit()
    pages = provider.render_pages(content, file_type)
    _advance(db, steps[render_key], "completed"); db.commit()

    project_info_dict: dict | None = None
    schedule_pages = pages  # default for single-page / image

    # ── Classify (multi-page only) ──────────────────────────────────────────
    extra_warnings: list[str] = []

    if is_multi:
        _advance(db, steps["Classifying document pages"], "active"); db.commit()
        classifications = provider.classify_pages(pages) if pages else []

        info_pages = [
            pages[c.page_index]
            for c in classifications
            if c.page_type in ("project_info", "title_sheet") and c.page_index < len(pages)
        ]

        # Tiered candidate selection — prefer specific over generic
        # Tier 1: explicitly window_schedule
        tier1 = [
            pages[c.page_index]
            for c in classifications
            if c.page_type == "window_schedule" and c.page_index < len(pages)
        ]
        # Tier 2: generic_schedule pages with a visible schedule table
        tier2 = [
            pages[c.page_index]
            for c in classifications
            if c.page_type == "generic_schedule"
            and c.contains_schedule_table
            and c.page_index < len(pages)
        ]
        # Tier 3: any page that may contain window/opening data
        tier3 = [
            pages[c.page_index]
            for c in classifications
            if c.may_contain_window_or_opening_data and c.page_index < len(pages)
        ]

        if tier1:
            schedule_pages = tier1
        elif tier2:
            schedule_pages = tier2
        elif tier3:
            schedule_pages = tier3
        else:
            schedule_pages = pages
            extra_warnings.append(
                "No confident schedule page was found; extraction attempted across all pages."
            )

        _advance(db, steps["Classifying document pages"], "completed"); db.commit()

        # ── Project info ────────────────────────────────────────────────────
        _advance(db, steps["Extracting project information"], "active"); db.commit()
        if info_pages:
            project_info_dict = provider.extract_project_info(info_pages)
        _advance(db, steps["Extracting project information"], "completed"); db.commit()

    # ── Window schedule ─────────────────────────────────────────────────────
    _advance(db, steps["Extracting window schedule"], "active"); db.commit()
    window_rows = provider.extract_window_schedule(schedule_pages) if schedule_pages else []
    _advance(db, steps["Extracting window schedule"], "completed"); db.commit()

    # ── Normalize: calculate area deterministically (never trust LLM area) ──
    _advance(db, steps["Normalizing extracted data"], "active"); db.commit()
    for row in window_rows:
        if not row.get("area"):
            computed = calculate_area(row.get("width"), row.get("height"))
            if computed:
                row["area"] = computed
    _advance(db, steps["Normalizing extracted data"], "completed"); db.commit()

    # ── Saving (mark active; caller does actual save then marks completed) ──
    _advance(db, steps["Saving extracted rows"], "active"); db.commit()

    warnings: list[str] = list(extra_warnings)
    if not window_rows:
        warnings.append(
            "No window rows were detected. "
            "Try uploading a file that contains a visible window schedule."
        )

    return ExtractionResult(
        window_rows=window_rows,
        warnings=warnings,
        project_info=project_info_dict,
    )


# ── Main orchestrator ─────────────────────────────────────────────────────────

def _run(session_id: str, file_path: str, file_type: str, db: DBSession) -> None:
    session = db.query(Session).filter(Session.id == session_id).first()
    if not session:
        raise RuntimeError(f"Session {session_id} not found.")

    # Close the upload-phase "Preparing extraction" step
    prep_step = (
        db.query(ProgressStep)
        .filter(ProgressStep.session_id == session_id, ProgressStep.name == "Preparing extraction")
        .first()
    )
    if prep_step:
        _advance(db, prep_step, "completed")
        db.commit()

    existing_count = (
        db.query(ProgressStep).filter(ProgressStep.session_id == session_id).count()
    )

    with open(file_path, "rb") as fh:
        content = fh.read()

    if file_type == "spreadsheet":
        result = _run_spreadsheet(session_id, content, file_path, db, existing_count)
    elif (
        file_type in ("single_page_pdf", "multi_page_pdf")
        and settings.llm_provider == "openai"
    ):
        result = _run_pdf_langchain(session_id, content, file_type, db, existing_count)
    else:
        result = _run_llm(session_id, content, file_type, db, existing_count)

    _save_project_info(db, session_id, result.project_info)
    _save_window_items(db, session_id, result.window_rows)

    # Mark "Saving extracted rows" complete
    saving_step = (
        db.query(ProgressStep)
        .filter(ProgressStep.session_id == session_id, ProgressStep.name == "Saving extracted rows")
        .order_by(ProgressStep.order_index.desc())
        .first()
    )
    if saving_step:
        _advance(db, saving_step, "completed")

    db.commit()


def run_extraction(session_id: str, file_path: str, file_type: str) -> None:
    """Entry point for FastAPI BackgroundTasks."""
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
                db.query(ProgressStep).filter(
                    ProgressStep.session_id == session_id,
                    ProgressStep.status == "active",
                ).update({"status": "error"})
                db.commit()
    finally:
        db.close()
