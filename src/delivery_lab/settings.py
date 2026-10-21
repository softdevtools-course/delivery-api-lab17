from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    database_path: Path
    session_ttl_hours: int = 24
    max_request_body_bytes: int = 64 * 1024

    @classmethod
    def from_env(cls) -> Settings:
        return cls(
            database_path=Path(os.environ.get("DELIVERY_LAB_DATABASE", "delivery.sqlite3")),
            session_ttl_hours=24,
            max_request_body_bytes=int(os.environ.get("DELIVERY_LAB_MAX_BODY_BYTES", 64 * 1024)),
        )
