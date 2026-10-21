from __future__ import annotations

import sqlite3
import time
import uuid
from datetime import UTC, datetime
from typing import Any, Callable

from starlette.responses import JSONResponse

from delivery_lab.database import get_connection


class RequestBodyTooLarge(Exception):
    pass


class RequestAuditMiddleware:
    def __init__(self, app: Any, database_path: str, max_body_bytes: int = 65_536) -> None:
        self.app = app
        self.database_path = database_path
        self.max_body_bytes = max_body_bytes

    async def __call__(self, scope: dict[str, Any], receive: Callable, send: Callable) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        request_id = str(uuid.uuid4())
        state = scope.setdefault("state", {})
        state["request_id"] = request_id
        started = time.perf_counter()
        status_code = 500
        response_started = False
        body_size = 0

        async def audited_send(message: dict[str, Any]) -> None:
            nonlocal status_code, response_started
            if message["type"] == "http.response.start":
                status_code = message["status"]
                response_started = True
                headers = list(message.get("headers", []))
                headers.append((b"x-request-id", request_id.encode("ascii")))
                message["headers"] = headers
            await send(message)

        async def limited_receive() -> dict[str, Any]:
            nonlocal body_size
            message = await receive()
            if message["type"] == "http.request":
                body_size += len(message.get("body", b""))
                if body_size > self.max_body_bytes:
                    raise RequestBodyTooLarge
            return message

        try:
            headers = {key.lower(): value for key, value in scope.get("headers", [])}
            content_length = headers.get(b"content-length")
            if content_length is not None and int(content_length) > self.max_body_bytes:
                response = JSONResponse({"detail": "Request body too large"}, status_code=413)
                await response(scope, receive, audited_send)
            else:
                await self.app(scope, limited_receive, audited_send)
        except RequestBodyTooLarge:
            if not response_started:
                response = JSONResponse({"detail": "Request body too large"}, status_code=413)
                await response(scope, receive, audited_send)
        finally:
            self._record(
                request_id=request_id,
                session_id=state.get("session_id"),
                method=scope.get("method", ""),
                route=getattr(scope.get("route"), "path", "<unmatched>"),
                status_code=status_code,
                duration_ms=(time.perf_counter() - started) * 1000,
                resource_id=state.get("resource_id"),
            )

    def _record(
        self,
        request_id: str,
        session_id: str | None,
        method: str,
        route: str,
        status_code: int,
        duration_ms: float,
        resource_id: str | None,
    ) -> None:
        try:
            with get_connection(self.database_path) as connection:
                connection.execute(
                    """INSERT INTO audit_log
                       (request_id, session_id, method, route, status_code, duration_ms, resource_id, occurred_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        request_id,
                        session_id,
                        method,
                        route,
                        status_code,
                        duration_ms,
                        resource_id,
                        datetime.now(UTC).isoformat(),
                    ),
                )
        except sqlite3.Error:
            # A failed audit insert should not replace the API response.
            return
