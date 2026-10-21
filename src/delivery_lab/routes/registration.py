from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel, StringConstraints

from delivery_lab.auth import authenticated_session, issue_session
from delivery_lab.domain import Session

router = APIRouter()
NonBlank = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]


class RegistrationRequest(BaseModel):
    surname: NonBlank
    first_name: NonBlank
    group_name: NonBlank


@router.post("/auth/register", status_code=status.HTTP_201_CREATED, tags=["Регистрация"])
def register(payload: RegistrationRequest, request: Request) -> dict[str, str]:
    session, token = issue_session(
        str(request.app.state.database_path),
        payload.surname,
        payload.first_name,
        payload.group_name,
        request.app.state.clock(),
    )
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_at": session.expires_at.isoformat(),
    }


@router.get("/me", tags=["Регистрация"])
def me(session: Session = Depends(authenticated_session)) -> dict[str, str]:
    return {
        "student_id": session.session_id,
        "surname": session.surname,
        "first_name": session.first_name,
        "group_name": session.group_name,
        "expires_at": session.expires_at.isoformat(),
    }
