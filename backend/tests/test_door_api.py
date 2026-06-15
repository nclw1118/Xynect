"""DB-backed API tests for door endpoints.

These hit the real Postgres configured via settings.database_url (the dev DB).
The whole module is skipped if the database is not reachable, so CI without a
DB still passes. Each test creates a throwaway session and cleans up after.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text

import app.models  # noqa: F401 — populate Base.metadata
from app.core.database import Base, SessionLocal, engine


def _db_available() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _db_available(), reason="Postgres not reachable")


@pytest.fixture()
def client_session():
    """Yield (TestClient, session_id) for a fresh review_ready session."""
    from fastapi.testclient import TestClient

    from app.main import app
    from app.models.door_item import DoorItem
    from app.models.project import ProjectInfo
    from app.models.session import Session as SessionModel
    from app.models.window_item import WindowItem

    # Ensure tables exist (idempotent on an already-migrated DB).
    Base.metadata.create_all(bind=engine)

    sid = str(uuid.uuid4())
    db = SessionLocal()
    db.add(SessionModel(id=sid, status="review_ready"))
    db.commit()
    db.close()

    client = TestClient(app)
    try:
        yield client, sid
    finally:
        db = SessionLocal()
        db.query(DoorItem).filter(DoorItem.session_id == sid).delete()
        db.query(WindowItem).filter(WindowItem.session_id == sid).delete()
        db.query(ProjectInfo).filter(ProjectInfo.session_id == sid).delete()
        db.query(SessionModel).filter(SessionModel.id == sid).delete()
        db.commit()
        db.close()


def test_get_extraction_returns_door_items_empty(client_session):
    client, sid = client_session
    resp = client.get(f"/api/sessions/{sid}/extraction")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["window_items"] == []
    assert body["door_items"] == []


def test_post_doors_creates_blank_door(client_session):
    client, sid = client_session

    resp = client.post(f"/api/sessions/{sid}/doors")
    assert resp.status_code == 200, resp.text
    door = resp.json()
    assert door["id"]
    assert door["material_type"] == "Door"
    assert door["tag"] is None

    # It now shows up in GET.
    got = client.get(f"/api/sessions/{sid}/extraction").json()
    assert len(got["door_items"]) == 1
    assert got["door_items"][0]["id"] == door["id"]


def test_patch_extraction_edits_door_fields(client_session):
    client, sid = client_session

    door = client.post(f"/api/sessions/{sid}/doors").json()
    door_id = door["id"]

    patch = {
        "door_items": [
            {
                "id": door_id,
                "tag": "D-1",
                "opening_type": "Single",
                "quantity": "2",
                "width": "3'-0\"",
                "height": "7'-0\"",
                "material": "Steel",
                "fire_rating": "90 MIN",
                "self_closing": "YES",
                "glass_type": "",
                "notes": "exterior entry",
            }
        ]
    }
    resp = client.patch(f"/api/sessions/{sid}/extraction", json=patch)
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "saved"

    got = client.get(f"/api/sessions/{sid}/extraction").json()
    saved = next(d for d in got["door_items"] if d["id"] == door_id)
    assert saved["tag"] == "D-1"
    assert saved["fire_rating"] == "90 MIN"
    assert saved["self_closing"] == "YES"
    assert saved["material"] == "Steel"
    assert saved["quantity"] == "2"


def test_patch_window_items_still_works(client_session):
    """Door support must not break window editing (backward compatibility)."""
    client, sid = client_session

    window = client.post(f"/api/sessions/{sid}/windows").json()
    patch = {"window_items": [{"id": window["id"], "tag": "W-1", "u_value": "0.30"}]}
    resp = client.patch(f"/api/sessions/{sid}/extraction", json=patch)
    assert resp.status_code == 200, resp.text

    got = client.get(f"/api/sessions/{sid}/extraction").json()
    saved = next(w for w in got["window_items"] if w["id"] == window["id"])
    assert saved["tag"] == "W-1"
    assert saved["u_value"] == "0.30"
    assert got["door_items"] == []
