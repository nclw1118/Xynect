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

    openai_api_key: str = ""
    anthropic_api_key: str = ""
    llm_provider: str = "stub"
    llm_model: str = "gpt-4.1"

    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
