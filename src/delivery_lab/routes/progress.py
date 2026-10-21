from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from delivery_lab.auth import authenticated_session
from delivery_lab.domain import Session
from delivery_lab.task_evaluator import get_progress, progress_dict

router = APIRouter()


@router.get("/progress", tags=["Задания"])
def progress(request: Request, session: Session = Depends(authenticated_session)) -> list[dict[str, str | bool]]:
    items = get_progress(request.app.state.database_path, session)
    return [progress_dict(item) for item in items]
