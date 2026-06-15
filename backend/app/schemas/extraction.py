from typing import Any, Optional

from pydantic import BaseModel


# ── Read schemas ──────────────────────────────────────────────────────────────

class ProjectInfoSchema(BaseModel):
    project_name: Optional[str] = None
    site_address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    detected_file_type: Optional[str] = None
    detected_relevant_pages: Optional[Any] = None


class WindowItemSchema(BaseModel):
    id: str
    tag: Optional[str] = None
    material_type: str = "Window"
    width: Optional[str] = None
    height: Optional[str] = None
    area: Optional[str] = None
    quantity: Optional[str] = None
    opening_type: Optional[str] = None
    material: Optional[str] = None
    u_value: Optional[str] = None
    shgc: Optional[str] = None
    vt: Optional[str] = None
    glass_type: Optional[str] = None
    confidence: float = 0.0
    notes: Optional[str] = None


class DoorItemSchema(BaseModel):
    id: str
    tag: Optional[str] = None
    material_type: str = "Door"
    width: Optional[str] = None
    height: Optional[str] = None
    area: Optional[str] = None
    quantity: Optional[str] = None
    opening_type: Optional[str] = None
    material: Optional[str] = None
    fire_rating: Optional[str] = None
    self_closing: Optional[str] = None
    glass_type: Optional[str] = None
    confidence: float = 0.0
    notes: Optional[str] = None


class ExtractionResponse(BaseModel):
    session_id: str
    project_info: Optional[ProjectInfoSchema] = None
    window_items: list[WindowItemSchema]
    # Defaults to [] so older clients / window-only sessions stay backward-compatible.
    door_items: list[DoorItemSchema] = []
    warnings: list[str]


# ── Patch schemas ─────────────────────────────────────────────────────────────

class PatchProjectInfo(BaseModel):
    project_name: Optional[str] = None
    site_address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None


class PatchWindowItem(BaseModel):
    id: str
    tag: Optional[str] = None
    width: Optional[str] = None
    height: Optional[str] = None
    area: Optional[str] = None
    quantity: Optional[str] = None
    opening_type: Optional[str] = None
    material: Optional[str] = None
    u_value: Optional[str] = None
    shgc: Optional[str] = None
    vt: Optional[str] = None
    glass_type: Optional[str] = None
    notes: Optional[str] = None


class PatchDoorItem(BaseModel):
    id: str
    tag: Optional[str] = None
    width: Optional[str] = None
    height: Optional[str] = None
    area: Optional[str] = None
    quantity: Optional[str] = None
    opening_type: Optional[str] = None
    material: Optional[str] = None
    fire_rating: Optional[str] = None
    self_closing: Optional[str] = None
    glass_type: Optional[str] = None
    notes: Optional[str] = None


class PatchExtractionRequest(BaseModel):
    project_info: Optional[PatchProjectInfo] = None
    window_items: Optional[list[PatchWindowItem]] = None
    door_items: Optional[list[PatchDoorItem]] = None


class PatchExtractionResponse(BaseModel):
    session_id: str
    status: str
