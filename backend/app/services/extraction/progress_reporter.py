"""Progress-step adapter for long-running extraction services.

Lets a service mark named steps active/completed/error without importing
the DB models directly. The orchestrator creates the reporter with a list of
step names; the service calls `start(name)` / `complete(name)` as it advances.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List

from sqlalchemy.orm import Session as DBSession

from app.models.progress_step import ProgressStep


class ProgressReporter:
    def __init__(
        self,
        db: DBSession,
        session_id: str,
        step_names: List[str],
        base_idx: int,
    ):
        self._db = db
        self._steps: Dict[str, ProgressStep] = {}
        for i, name in enumerate(step_names):
            step = ProgressStep(
                session_id=session_id,
                name=name,
                status="pending",
                order_index=base_idx + i,
            )
            db.add(step)
            self._steps[name] = step
        db.flush()
        db.commit()

    def start(self, name: str) -> None:
        step = self._steps.get(name)
        if step is None:
            return
        step.status = "active"
        step.updated_at = datetime.now(timezone.utc)
        self._db.flush()
        self._db.commit()

    def complete(self, name: str) -> None:
        step = self._steps.get(name)
        if step is None:
            return
        step.status = "completed"
        step.updated_at = datetime.now(timezone.utc)
        self._db.flush()
        self._db.commit()

    def error(self, name: str) -> None:
        step = self._steps.get(name)
        if step is None:
            return
        step.status = "error"
        step.updated_at = datetime.now(timezone.utc)
        self._db.flush()
        self._db.commit()
