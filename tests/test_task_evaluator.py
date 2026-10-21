import sqlite3

from fastapi.testclient import TestClient

from delivery_lab.main import create_app


def register(client: TestClient, surname: str = "Иванов", first_name: str = "Иван") -> str:
    response = client.post(
        "/auth/register",
        json={"surname": surname, "first_name": first_name, "group_name": "23-ИС-1"},
    )
    assert response.status_code == 201
    return response.json()["access_token"]


def headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def progress_by_code(client: TestClient, token: str) -> dict[str, dict]:
    response = client.get("/progress", headers=headers(token))
    assert response.status_code == 200
    return {item["task_code"]: item for item in response.json()}


def target_id(database_path, session_id: str, task_code: str) -> str:
    with sqlite3.connect(database_path) as connection:
        row = connection.execute(
            "SELECT target_shipment_id FROM tasks WHERE session_id = ? AND task_code = ?",
            (session_id, task_code),
        ).fetchone()
    return row[0]


def test_cancel_task_requires_personal_target_cancelled(tmp_path):
    database_path = tmp_path / "delivery.sqlite3"
    client = TestClient(create_app(database_path))
    token = register(client)

    before = progress_by_code(client, token)
    target = next(
        item for item in client.get("/shipments", headers=headers(token)).json()
        if item["recipient_name"] == "Иванов Иван Иванович"
    )
    client.post(f"/shipments/{target['shipment_id']}/cancel", headers=headers(token))
    after = progress_by_code(client, token)

    assert before["cancel_shipment"]["completed"] is False
    assert after["cancel_shipment"]["completed"] is True
    assert "target_shipment_id" not in after["cancel_shipment"]


def test_tracking_task_requires_successful_target_lookup_and_history(tmp_path):
    database_path = tmp_path / "delivery.sqlite3"
    client = TestClient(create_app(database_path))
    token = register(client)
    profile = client.get("/me", headers=headers(token)).json()
    shipment_id = target_id(database_path, profile["student_id"], "inspect_tracking")

    history = client.get(f"/shipments/{shipment_id}/tracking", headers=headers(token))
    assert history.status_code == 200
    assert progress_by_code(client, token)["inspect_tracking"]["completed"] is False

    lookup = client.get("/shipments", headers=headers(token))
    assert lookup.status_code == 200
    assert progress_by_code(client, token)["inspect_tracking"]["completed"] is True


def test_update_task_requires_expected_delivery(tmp_path):
    client = TestClient(create_app(tmp_path / "delivery.sqlite3"))
    token = register(client)
    shipments = client.get("/shipments", headers=headers(token)).json()
    target = next(item for item in shipments if item["recipient_name"] == "Сидоров Сидор Сидорович")

    wrong = client.patch(
        f"/shipments/{target['shipment_id']}",
        headers=headers(token),
        json={"delivery_method": "pickup_point", "pickup_point_id": "cheb-001"},
    )
    assert wrong.status_code == 200
    assert progress_by_code(client, token)["update_delivery"]["completed"] is False

    correct = client.patch(
        f"/shipments/{target['shipment_id']}",
        headers=headers(token),
        json={"delivery_method": "pickup_point", "pickup_point_id": "cheb-003"},
    )
    assert correct.status_code == 200
    assert progress_by_code(client, token)["update_delivery"]["completed"] is True


def test_create_task_requires_new_shipment_at_expected_point(tmp_path):
    client = TestClient(create_app(tmp_path / "delivery.sqlite3"))
    token = register(client)

    wrong = client.post(
        "/shipments",
        headers=headers(token),
        json={"recipient_name": "Новый Клиент", "delivery_method": "pickup_point", "pickup_point_id": "cheb-001"},
    )
    assert wrong.status_code == 201
    assert progress_by_code(client, token)["create_shipment"]["completed"] is False

    correct = client.post(
        "/shipments",
        headers=headers(token),
        json={"recipient_name": "Другой Клиент", "delivery_method": "pickup_point", "pickup_point_id": "cheb-002"},
    )
    assert correct.status_code == 201
    assert progress_by_code(client, token)["create_shipment"]["completed"] is True


def test_other_session_with_same_name_cannot_complete_task(tmp_path):
    client = TestClient(create_app(tmp_path / "delivery.sqlite3"))
    first = register(client, "Иванов", "Иван")
    second = register(client, "Иванов", "Иван")
    first_profile = client.get("/me", headers=headers(first)).json()
    first_target = target_id(client.app.state.database_path, first_profile["student_id"], "cancel_shipment")

    response = client.post(f"/shipments/{first_target}/cancel", headers=headers(first))

    assert response.status_code == 200
    assert progress_by_code(client, first)["cancel_shipment"]["completed"] is True
    assert progress_by_code(client, second)["cancel_shipment"]["completed"] is False
