from datetime import UTC, datetime, timedelta
import sqlite3

from fastapi.testclient import TestClient

from delivery_lab.main import create_app


def register(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/auth/register",
        json={"surname": "Иванов", "first_name": "Иван", "group_name": "23-ИС-1"},
    )
    assert response.status_code == 201
    return response.json()


def test_session_token_valid_until_24_hours(tmp_path):
    now = datetime(2026, 10, 21, 9, 0, tzinfo=UTC)
    clock = {"now": now}
    client = TestClient(create_app(tmp_path / "delivery.sqlite3", clock=lambda: clock["now"]))
    session = register(client)
    headers = {"Authorization": f"Bearer {session['access_token']}"}

    clock["now"] = now + timedelta(hours=23, minutes=59, seconds=59)
    assert client.get("/me", headers=headers).status_code == 200

    clock["now"] = now + timedelta(hours=24)
    response = client.get("/me", headers=headers)
    assert response.status_code == 401


def test_repeat_registration_creates_independent_seed_data(tmp_path):
    database_path = tmp_path / "delivery.sqlite3"
    client = TestClient(create_app(database_path))
    first = register(client)
    second = register(client)

    assert first["access_token"] != second["access_token"]
    with sqlite3.connect(database_path) as connection:
        rows = connection.execute(
            "SELECT session_id, token_hash FROM sessions ORDER BY issued_at"
        ).fetchall()
        shipment_sets = [
            {
                row[0]
                for row in connection.execute(
                    "SELECT shipment_id FROM shipments WHERE session_id = ?", (session_id,)
                ).fetchall()
            }
            for session_id, _ in rows
        ]

    assert len(rows) == 2
    assert rows[0][0] != rows[1][0]
    assert rows[0][1] != first["access_token"]
    assert rows[1][1] != second["access_token"]
    assert shipment_sets[0]
    assert shipment_sets[1]
    assert shipment_sets[0].isdisjoint(shipment_sets[1])


def test_me_returns_authenticated_student_profile(tmp_path):
    client = TestClient(create_app(tmp_path / "delivery.sqlite3"))
    session = register(client)

    response = client.get(
        "/me", headers={"Authorization": f"Bearer {session['access_token']}"}
    )

    assert response.status_code == 200
    assert response.json()["surname"] == "Иванов"
    assert response.json()["first_name"] == "Иван"
    assert response.json()["group_name"] == "23-ИС-1"


def test_registration_rejects_blank_identity_fields(tmp_path):
    client = TestClient(create_app(tmp_path / "delivery.sqlite3"))

    response = client.post(
        "/auth/register",
        json={"surname": " ", "first_name": "Иван", "group_name": "23-ИС-1"},
    )

    assert response.status_code == 422
