from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.api.sessions import router as sessions_router
from app.api.extraction import router as extraction_router

app = FastAPI(title="Xynect API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.next_public_api_base_url, "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(sessions_router)
app.include_router(extraction_router)


@app.get("/api/health")
def health():
    return {"status": "ok", "llm_provider": settings.llm_provider}
