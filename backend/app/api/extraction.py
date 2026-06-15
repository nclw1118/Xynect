import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session as DBSession

from app.core.database import get_db
from app.models.door_item import DoorItem
from app.models.project import ProjectInfo
from app.models.session import Session
from app.models.window_item import WindowItem
from app.schemas.extraction import (
    DoorItemSchema,
    ExtractionResponse,
    PatchExtractionRequest,
    PatchExtractionResponse,
    ProjectInfoSchema,
    WindowItemSchema,
)

router = APIRouter(prefix="/api/sessions", tags=["extraction"])

_EDITABLE_WINDOW_FIELDS = [
    "tag", "width", "height", "area", "quantity",
    "opening_type", "material", "u_value", "shgc", "vt", "glass_type", "notes",
]

_EDITABLE_DOOR_FIELDS = [
    "tag", "opening_type", "quantity", "width", "height", "area",
    "material", "fire_rating", "self_closing", "glass_type", "notes",
]


def _to_door_schema(item: DoorItem) -> DoorItemSchema:
    return DoorItemSchema(
        id=item.id,
        tag=item.tag,
        material_type=item.material_type,
        width=item.width,
        height=item.height,
        area=item.area,
        quantity=item.quantity,
        opening_type=item.opening_type,
        material=item.material,
        fire_rating=item.fire_rating,
        self_closing=item.self_closing,
        glass_type=item.glass_type,
        confidence=item.confidence,
        notes=item.notes,
    )


@router.get("/{session_id}/extraction", response_model=ExtractionResponse)
def get_extraction(session_id: str, db: DBSession = Depends(get_db)) -> ExtractionResponse:
    session = db.query(Session).filter(Session.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")

    if session.status not in {"review_ready", "confirmed", "recommendation_ready"}:
        raise HTTPException(
            status_code=409,
            detail=f"Extraction is not ready yet. Session status: {session.status}",
        )

    project = db.query(ProjectInfo).filter(ProjectInfo.session_id == session_id).first()
    items = (
        db.query(WindowItem)
        .filter(WindowItem.session_id == session_id)
        .order_by(WindowItem.created_at)
        .all()
    )
    door_items = (
        db.query(DoorItem)
        .filter(DoorItem.session_id == session_id)
        .order_by(DoorItem.created_at)
        .all()
    )

    warnings: list[str] = []
    if session.error_message:
        warnings.append(session.error_message)

    project_schema: ProjectInfoSchema | None = None
    if project:
        project_schema = ProjectInfoSchema(
            project_name=project.project_name,
            site_address=project.site_address,
            city=project.city,
            state=project.state,
            zip_code=project.zip_code,
            detected_file_type=project.detected_file_type or session.uploaded_file_type,
            detected_relevant_pages=project.detected_relevant_pages,
        )

    window_schemas = [
        WindowItemSchema(
            id=item.id,
            tag=item.tag,
            material_type=item.material_type,
            width=item.width,
            height=item.height,
            area=item.area,
            quantity=item.quantity,
            opening_type=item.opening_type,
            material=item.material,
            u_value=item.u_value,
            shgc=item.shgc,
            vt=item.vt,
            glass_type=item.glass_type,
            confidence=item.confidence,
            notes=item.notes,
        )
        for item in items
    ]

    door_schemas = [_to_door_schema(item) for item in door_items]

    return ExtractionResponse(
        session_id=session_id,
        project_info=project_schema,
        window_items=window_schemas,
        door_items=door_schemas,
        warnings=warnings,
    )


@router.patch("/{session_id}/extraction", response_model=PatchExtractionResponse)
def patch_extraction(
    session_id: str,
    body: PatchExtractionRequest,
    db: DBSession = Depends(get_db),
) -> PatchExtractionResponse:
    session = db.query(Session).filter(Session.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")

    if session.status not in {"review_ready", "confirmed", "recommendation_ready"}:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot edit extraction in status: {session.status}",
        )

    # ── Update project info ───────────────────────────────────────────────
    if body.project_info is not None:
        project = db.query(ProjectInfo).filter(ProjectInfo.session_id == session_id).first()
        if project:
            patch = body.project_info.model_dump(exclude_unset=True)
            for k, v in patch.items():
                setattr(project, k, v)

    # ── Update window items ───────────────────────────────────────────────
    if body.window_items:
        for patch_item in body.window_items:
            db_item = db.query(WindowItem).filter(WindowItem.id == patch_item.id).first()
            if not db_item:
                continue

            original = db_item.original_extraction or {}
            user_edits = dict(db_item.user_edits or {})

            patch_fields = patch_item.model_dump(exclude={"id"}, exclude_unset=True)
            for field_name, new_value in patch_fields.items():
                if field_name not in _EDITABLE_WINDOW_FIELDS:
                    continue
                original_value = original.get(field_name)
                edited = new_value != original_value
                user_edits[field_name] = {
                    "original_value": original_value,
                    "current_value": new_value,
                    "edited_by_user": edited,
                }
                setattr(db_item, field_name, new_value)

            db_item.user_edits = user_edits
            db_item.updated_at = datetime.now(timezone.utc)

    # ── Update door items ─────────────────────────────────────────────────
    if body.door_items:
        for patch_item in body.door_items:
            db_item = db.query(DoorItem).filter(DoorItem.id == patch_item.id).first()
            if not db_item:
                continue

            original = db_item.original_extraction or {}
            user_edits = dict(db_item.user_edits or {})

            patch_fields = patch_item.model_dump(exclude={"id"}, exclude_unset=True)
            for field_name, new_value in patch_fields.items():
                if field_name not in _EDITABLE_DOOR_FIELDS:
                    continue
                original_value = original.get(field_name)
                edited = new_value != original_value
                user_edits[field_name] = {
                    "original_value": original_value,
                    "current_value": new_value,
                    "edited_by_user": edited,
                }
                setattr(db_item, field_name, new_value)

            db_item.user_edits = user_edits
            db_item.updated_at = datetime.now(timezone.utc)

    db.commit()
    return PatchExtractionResponse(session_id=session_id, status="saved")


@router.post("/{session_id}/windows", response_model=WindowItemSchema)
def add_window(session_id: str, db: DBSession = Depends(get_db)) -> WindowItemSchema:
    session = db.query(Session).filter(Session.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")

    if session.status not in {"review_ready", "confirmed", "recommendation_ready"}:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot add window in session status: {session.status}",
        )

    item = WindowItem(
        id=str(uuid.uuid4()),
        session_id=session_id,
        material_type="Window",
        confidence=0.0,
        notes="Manually added by user",
        original_extraction={},
        user_edits={},
    )
    db.add(item)
    db.commit()
    db.refresh(item)

    return WindowItemSchema(
        id=item.id,
        tag=item.tag,
        material_type=item.material_type,
        width=item.width,
        height=item.height,
        area=item.area,
        quantity=item.quantity,
        opening_type=item.opening_type,
        material=item.material,
        u_value=item.u_value,
        shgc=item.shgc,
        vt=item.vt,
        glass_type=item.glass_type,
        confidence=item.confidence,
        notes=item.notes,
    )


@router.post("/{session_id}/doors", response_model=DoorItemSchema)
def add_door(session_id: str, db: DBSession = Depends(get_db)) -> DoorItemSchema:
    session = db.query(Session).filter(Session.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")

    if session.status not in {"review_ready", "confirmed", "recommendation_ready"}:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot add door in session status: {session.status}",
        )

    item = DoorItem(
        id=str(uuid.uuid4()),
        session_id=session_id,
        material_type="Door",
        confidence=0.0,
        notes="Manually added by user",
        original_extraction={},
        user_edits={},
    )
    db.add(item)
    db.commit()
    db.refresh(item)

    return _to_door_schema(item)
