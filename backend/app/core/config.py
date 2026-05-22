from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Resolves to the project root (Xynect/) regardless of CWD.
# config.py lives at backend/app/core/config.py → 4 parents up = project root.
_ENV_FILE = Path(__file__).resolve().parent.parent.parent.parent / ".env"


class Settings(BaseSettings):
    database_url: str = "postgresql://xynect:xynect_password@localhost:5432/xynect_mvp"
    backend_port: int = 8000
    upload_dir: str = "./storage/uploads"
    session_ttl_hours: int = 24
    max_upload_mb: int = 75

    next_public_api_base_url: str = "http://localhost:8000"
    frontend_url: str = "http://localhost:3000"

    openai_api_key: str = ""
    anthropic_api_key: str = ""
    llm_provider: str = "stub"
    llm_model: str = "gpt-4.1"

    # PDF extraction tuning (LangChain crop-planning algorithm)
    pdf_render_dpi: int = 150
    pdf_crop_dpi: int = 150
    pdf_overlay_dpi: int = 120
    pdf_crop_expand_ratio: float = 0.05
    pdf_max_crop_regions_per_page: int = 3
    pdf_min_crop_area_ratio: float = 0.01
    pdf_max_crop_area_ratio: float = 0.90
    pdf_strong_title_threshold: float = 85.0
    pdf_top_native_text_backup_pages: int = 5
    pdf_max_candidate_pages_sent_to_llm: int = 8
    pdf_debug_output_dir: str = "./storage/extraction_debug"
    pdf_save_debug_artifacts: bool = True

    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
