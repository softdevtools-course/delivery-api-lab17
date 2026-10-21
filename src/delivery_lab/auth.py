from __future__ import annotations

from datetime import UTC, datetime, timedelta
import hashlib
import secrets
import sqlite3
import uuid

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from delivery_lab.database import get_connection
from delivery_lab.domain import Session
from delivery_lab.seed import iso_utc, seed_session

bearer_scheme = HTTPBearer(auto_error=False, scheme_name="BearerAuth")


def normalize_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def token_digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def issue_session(
    database_path: str,
    surname: str,
    first_name: str,
    group_name: str,
    now: datetime,
) -> tuple[Session, str]:
    issued_at = normalize_datetime(now)
    expires_at = issued_at + timedelta(hours=24)
    session_id = str(uuid.uuid4())
    token = secrets.token_urlsafe(32)
    with get_connection(database_path) as connection:
        connection.execute(
            """INSERT INTO sessions
               (session_id, surname, first_name, group_name, token_hash, issued_at, expires_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                session_id,
                surname,
                first_name,
                group_name,
                token_digest(token),
                iso_utc(issued_at),
                iso_utc(expires_at),
            ),
        )
        seed_session(connection, session_id, issued_at)
    return Session(session_id, surname, first_name, group_name, issued_at, expires_at), token


def require_session(database_path: str, authorization: str | None, now: datetime) -> Session:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Bearer token required", headers={"WWW-Authenticate": "Bearer"})
    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(status_code=401, detail="Bearer token required", headers={"WWW-Authenticate": "Bearer"})
    with get_connection(database_path) as connection:
        row = connection.execute(
            """SELECT session_id, surname, first_name, group_name, issued_at, expires_at
               FROM sessions WHERE token_hash = ?""",
            (token_digest(token),),
        ).fetchone()
    if row is None:
        raise HTTPException(status_code=401, detail="Invalid or expired bearer token", headers={"WWW-Authenticate": "Bearer"})
    issued_at = datetime.fromisoformat(row["issued_at"])
    expires_at = datetime.fromisoformat(row["expires_at"])
    if normalize_datetime(now) >= expires_at:
        raise HTTPException(status_code=401, detail="Invalid or expired bearer token", headers={"WWW-Authenticate": "Bearer"})
    return Session(
        row["session_id"], row["surname"], row["first_name"], row["group_name"], issued_at, expires_at
    )


def authenticated_session(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> Session:
    authorization = None
    if credentials is not None:
        authorization = f"{credentials.scheme} {credentials.credentials}"
    session = require_session(
        str(request.app.state.database_path), authorization, request.app.state.clock()
    )
    request.state.session_id = session.session_id
    return session
