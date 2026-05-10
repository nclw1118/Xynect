from typing import Optional

from pydantic import BaseModel


class UploadResponse(BaseModel):
    session_id: str
    status: str
    message: str


class ProgressStepSchema(BaseModel):
    name: str
    status: str  # pending | active | completed | error


class ProgressResponse(BaseModel):
    session_id: str
    status: str
    current_step: Optional[str]
    steps: list[ProgressStepSchema]
