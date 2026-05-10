"""
Idempotent fake supplier seed.

Run with:
    cd backend
    source .venv/bin/activate
    python -m app.seed.suppliers
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from app.core.database import SessionLocal
from app.models.supplier import Supplier

FAKE_SUPPLIERS = [
    {
        "name": "Northline Glass Supply",
        "supported_states": ["NY", "MI"],
        "supported_material_types": ["Window"],
        "supported_opening_types": ["Casement", "Fixed", "Single-Hung"],
        "supported_window_materials": ["Aluminum", "Vinyl"],
        "supported_glass_types": ["Clear", "Low-E"],
        "min_width": 12.0,
        "max_width": 72.0,
        "min_height": 12.0,
        "max_height": 84.0,
        "base_unit_price": 420.0,
        "lead_time_days": 14,
        "reliability_score": 0.92,
        "notes": "Strong regional presence in NY and MI. Specializes in aluminum casement windows.",
    },
    {
        "name": "BlueRidge Window Co.",
        "supported_states": ["NY", "FL"],
        "supported_material_types": ["Window"],
        "supported_opening_types": ["Fixed", "Awning", "Casement"],
        "supported_window_materials": ["Aluminum", "Fiberglass"],
        "supported_glass_types": ["Clear", "Tinted"],
        "min_width": 18.0,
        "max_width": 96.0,
        "min_height": 18.0,
        "max_height": 96.0,
        "base_unit_price": 380.0,
        "lead_time_days": 21,
        "reliability_score": 0.85,
        "notes": "Lower-cost option. Longer lead time may create scheduling risk on tight projects.",
    },
    {
        "name": "MetroFrame Systems",
        "supported_states": ["MI", "NY"],
        "supported_material_types": ["Window"],
        "supported_opening_types": ["Casement", "Double-Hung", "Single-Hung"],
        "supported_window_materials": ["Steel", "Aluminum"],
        "supported_glass_types": ["Low-E", "Clear"],
        "min_width": 12.0,
        "max_width": 60.0,
        "min_height": 12.0,
        "max_height": 72.0,
        "base_unit_price": 510.0,
        "lead_time_days": 10,
        "reliability_score": 0.95,
        "notes": "Fastest lead time. Specializes in steel and aluminum commercial framing.",
    },
    {
        "name": "ClearView Building Products",
        "supported_states": ["FL", "MI"],
        "supported_material_types": ["Window"],
        "supported_opening_types": ["Fixed", "Sliding", "Picture"],
        "supported_window_materials": ["Vinyl", "Fiberglass"],
        "supported_glass_types": ["Clear", "Low-E"],
        "min_width": 24.0,
        "max_width": 120.0,
        "min_height": 24.0,
        "max_height": 120.0,
        "base_unit_price": 340.0,
        "lead_time_days": 18,
        "reliability_score": 0.88,
        "notes": "Best for large fixed and sliding windows. Competitive pricing on vinyl.",
    },
    {
        "name": "Sunbelt Architectural Windows",
        "supported_states": ["FL"],
        "supported_material_types": ["Window"],
        "supported_opening_types": ["Casement", "Fixed", "Awning", "Jalousie"],
        "supported_window_materials": ["Aluminum", "Wood"],
        "supported_glass_types": ["Tinted", "Clear"],
        "min_width": 12.0,
        "max_width": 84.0,
        "min_height": 12.0,
        "max_height": 96.0,
        "base_unit_price": 460.0,
        "lead_time_days": 25,
        "reliability_score": 0.82,
        "notes": "Florida-only. Good for impact-rated and hurricane-zone requirements.",
    },
]


def seed_suppliers() -> None:
    db = SessionLocal()
    try:
        inserted = 0
        updated = 0
        for data in FAKE_SUPPLIERS:
            existing = db.query(Supplier).filter(Supplier.name == data["name"]).first()
            if existing:
                for key, value in data.items():
                    setattr(existing, key, value)
                updated += 1
            else:
                db.add(Supplier(**data))
                inserted += 1
        db.commit()
        print(f"Seed complete: {inserted} inserted, {updated} updated.")
    except Exception as exc:
        db.rollback()
        print(f"Seed failed: {exc}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_suppliers()
