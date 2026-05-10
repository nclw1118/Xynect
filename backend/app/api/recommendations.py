import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session as DBSession

from app.core.database import get_db
from app.models.project import ProjectInfo
from app.models.recommendation import Recommendation
from app.models.session import Session
from app.models.supplier import Supplier
from app.models.window_item import WindowItem
from app.schemas.recommendation import ConfirmResponse, QuoteRow, RecommendationsResponse
from app.services.recommendation_writer import generate_summary
from app.services.supplier_matching import match_all

router = APIRouter(prefix="/api/sessions", tags=["recommendations"])


@router.post("/{session_id}/confirm", response_model=ConfirmResponse)
def confirm_session(session_id: str, db: DBSession = Depends(get_db)) -> ConfirmResponse:
    session = db.query(Session).filter(Session.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")

    if session.status not in {"review_ready", "confirmed"}:
        raise HTTPException(
            status_code=409,
            detail=f"Session cannot be confirmed from status '{session.status}'.",
        )

    window_items = (
        db.query(WindowItem).filter(WindowItem.session_id == session_id).all()
    )
    if not window_items:
        raise HTTPException(
            status_code=422,
            detail="No window items found. Upload a file with extractable window data first.",
        )

    # Resolve state from ProjectInfo
    project = db.query(ProjectInfo).filter(ProjectInfo.session_id == session_id).first()
    state: str | None = project.state if project else None

    suppliers = db.query(Supplier).all()

    # Delete any stale recommendations from a previous confirm
    db.query(Recommendation).filter(Recommendation.session_id == session_id).delete()

    # Run matching
    tag_results = match_all(window_items, suppliers, state, top_n=3)

    # Persist Recommendation rows
    for item in window_items:
        tag = item.tag or f"item_{item.id[:6]}"
        for result in tag_results.get(tag, []):
            db.add(
                Recommendation(
                    id=result.recommendation_id,
                    session_id=session_id,
                    window_item_id=item.id,
                    supplier_id=result.supplier.id,
                    tag=result.tag,
                    unit_price=result.unit_price,
                    quantity=result.quantity,
                    estimated_total=result.estimated_total,
                    lead_time_days=result.supplier.lead_time_days,
                    match_score=result.match_score,
                    match_reason=result.match_reason,
                    risk_notes=result.risk_notes,
                )
            )

    session.status = "recommendation_ready"
    db.commit()

    return ConfirmResponse(
        session_id=session_id,
        status="recommendation_ready",
        next=f"/recommendations/{session_id}",
    )


@router.get("/{session_id}/recommendations", response_model=RecommendationsResponse)
def get_recommendations(
    session_id: str, db: DBSession = Depends(get_db)
) -> RecommendationsResponse:
    session = db.query(Session).filter(Session.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")

    if session.status != "recommendation_ready":
        raise HTTPException(
            status_code=409,
            detail=f"Recommendations not ready. Session status: {session.status}",
        )

    recs = (
        db.query(Recommendation, Supplier)
        .join(Supplier, Recommendation.supplier_id == Supplier.id)
        .filter(Recommendation.session_id == session_id)
        .order_by(Recommendation.tag, Recommendation.match_score.desc())
        .all()
    )

    quote_rows = [
        QuoteRow(
            tag=rec.tag,
            supplier=sup.name,
            unit_price=rec.unit_price,
            quantity=rec.quantity,
            estimated_total=rec.estimated_total,
            lead_time_days=rec.lead_time_days,
            match_score=rec.match_score,
            match_reason=rec.match_reason,
            risk_notes=rec.risk_notes,
        )
        for rec, sup in recs
    ]

    # Re-run in-memory to build tag_results for NL summary
    window_items = (
        db.query(WindowItem).filter(WindowItem.session_id == session_id).all()
    )
    project = db.query(ProjectInfo).filter(ProjectInfo.session_id == session_id).first()
    state = project.state if project else None
    suppliers = db.query(Supplier).all()
    tag_results = match_all(window_items, suppliers, state, top_n=3)

    summary = generate_summary(tag_results)

    return RecommendationsResponse(
        session_id=session_id,
        quote_table=quote_rows,
        natural_language_summary=summary,
    )
