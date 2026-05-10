from pydantic import BaseModel


class ConfirmResponse(BaseModel):
    session_id: str
    status: str
    next: str


class QuoteRow(BaseModel):
    tag: str
    supplier: str
    unit_price: float
    quantity: int
    estimated_total: float
    lead_time_days: int
    match_score: float        # 0.0 – 1.0
    match_reason: str
    risk_notes: str


class RecommendationsResponse(BaseModel):
    session_id: str
    quote_table: list[QuoteRow]
    natural_language_summary: str
