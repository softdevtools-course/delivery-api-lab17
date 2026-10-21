import sqlite3

from fastapi.testclient import TestClient

from delivery_lab.main import create_app


def test_health_returns_ok(tmp_path):
    database_path = tmp_path / "delivery.sqlite3"
    client = TestClient(create_app(database_path=database_path))

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_schema_is_initialized(tmp_path):
    database_path = tmp_path / "delivery.sqlite3"
    create_app(database_path=database_path)

    with sqlite3.connect(database_path) as connection:
        table_names = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }

    assert {
        "sessions",
        "pickup_points",
        "shipments",
        "tracking_events",
        "tasks",
        "audit_log",
    } <= table_names
