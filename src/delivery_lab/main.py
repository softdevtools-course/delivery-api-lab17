from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Callable

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from delivery_lab.audit import RequestAuditMiddleware
from delivery_lab.database import initialize_database
from delivery_lab.routes.pickup_points import router as pickup_points_router
from delivery_lab.routes.progress import router as progress_router
from delivery_lab.routes.registration import router as registration_router
from delivery_lab.routes.shipments import router as shipments_router
from delivery_lab.settings import Settings
from delivery_lab.seed import TASK_DEFINITIONS

PACKAGE_DIR = Path(__file__).parent
templates = Jinja2Templates(directory=str(PACKAGE_DIR / "templates"))


def create_app(
    database_path: str | Path | None = None,
    clock: Callable[[], datetime] | None = None,
) -> FastAPI:
    settings = Settings.from_env()
    if database_path is not None:
        settings = Settings(database_path=Path(database_path))
    initialize_database(settings.database_path)

    app = FastAPI(title="Учебная служба доставки", version="0.1.0", docs_url=None, redoc_url=None)
    app.state.settings = settings
    app.state.database_path = settings.database_path
    app.state.clock = clock or (lambda: datetime.now(UTC))
    app.mount("/static", StaticFiles(directory=str(PACKAGE_DIR / "static")), name="static")
    app.add_middleware(
        RequestAuditMiddleware,
        database_path=str(settings.database_path),
        max_body_bytes=settings.max_request_body_bytes,
    )

    @app.get("/health", tags=["Служебное"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/docs", include_in_schema=False, response_class=HTMLResponse)
    def docs(request: Request) -> HTMLResponse:
        return templates.TemplateResponse(
            request=request,
            name="docs.html",
            context={
                "title": app.title,
                "tasks": [
                    {"task_code": code, "title": title, "description": description}
                    for code, title, description in TASK_DEFINITIONS
                ],
            },
        )

    app.include_router(registration_router)
    app.include_router(pickup_points_router)
    app.include_router(progress_router)
    app.include_router(shipments_router)
    return app


app = create_app()
