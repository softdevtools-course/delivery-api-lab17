import sqlite3

from fastapi.testclient import TestClient

from delivery_lab.main import create_app


def test_audit_records_request_metadata_without_token_or_pii(tmp_path):
    database_path = tmp_path / "delivery.sqlite3"
    client = TestClient(create_app(database_path))
    registration = client.post(
        "/auth/register",
        json={"surname": "Иванов", "first_name": "Иван", "group_name": "23-ИС-1"},
    ).json()
    token = registration["access_token"]
    response = client.get("/shipments", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    request_id = response.headers["x-request-id"]
    with sqlite3.connect(database_path) as connection:
        record = connection.execute(
            "SELECT method, route, status_code, resource_id, session_id, duration_ms FROM audit_log WHERE request_id = ?",
            (request_id,),
        ).fetchone()
        columns = {row[1] for row in connection.execute("PRAGMA table_info(audit_log)")}

    assert record[:3] == ("GET", "/shipments", 200)
    assert record[4] is not None
    assert record[5] >= 0
    assert "access_token" not in columns
    assert "recipient_name" not in columns
    assert "delivery_address" not in columns


def test_oversized_request_body_is_rejected_and_audited(tmp_path):
    database_path = tmp_path / "delivery.sqlite3"
    client = TestClient(create_app(database_path))
    registration = client.post(
        "/auth/register",
        json={"surname": "Иванов", "first_name": "Иван", "group_name": "23-ИС-1"},
    ).json()

    response = client.post(
        "/shipments",
        headers={"Authorization": f"Bearer {registration['access_token']}"},
        json={"recipient_name": "x" * 70_000, "delivery_method": "courier", "delivery_address": "адрес"},
    )

    assert response.status_code == 413
    with sqlite3.connect(database_path) as connection:
        record = connection.execute(
            "SELECT status_code FROM audit_log WHERE request_id = ?",
            (response.headers["x-request-id"],),
        ).fetchone()
    assert record == (413,)
