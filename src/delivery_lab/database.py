from __future__ import annotations

import sqlite3
from pathlib import Path

from delivery_lab.settings import Settings

PICKUP_POINTS = (
    ("cheb-001", "Чебоксары", "ул. Гузовского, 16"),
    ("cheb-002", "Чебоксары", "ул. Водопроводная, 22"),
    ("cheb-003", "Чебоксары", "ул. Ленинского комсомола, 23к3"),
)


def get_connection(database_path: str | Path) -> sqlite3.Connection:
    connection = sqlite3.connect(database_path, check_same_thread=False)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize_database(database_path: str | Path) -> None:
    path = Path(database_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    schema = Path(__file__).with_name("schema.sql").read_text(encoding="utf-8")
    with get_connection(path) as connection:
        connection.executescript(schema)
        connection.executemany(
            "INSERT OR IGNORE INTO pickup_points (pickup_point_id, city, address) VALUES (?, ?, ?)",
            PICKUP_POINTS,
        )


def initialize_from_settings(settings: Settings) -> None:
    initialize_database(settings.database_path)
