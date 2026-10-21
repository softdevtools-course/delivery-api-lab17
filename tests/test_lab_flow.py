from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from delivery_lab.main import create_app


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_four_task_flows_update_progress(tmp_path):
    client = TestClient(create_app(tmp_path / "delivery.sqlite3"))
    registration = client.post(
        "/auth/register",
        json={"surname": "Иванов", "first_name": "Иван", "group_name": "23-ИС-1"},
    )
    assert registration.status_code == 201
    token = registration.json()["access_token"]
    headers = _headers(token)

    shipments = client.get("/shipments", headers=headers).json()
    assert len(client.get("/pickup-points", headers=headers).json()) == 3
    progress = {task["task_code"]: task for task in client.get("/progress", headers=headers).json()}
    assert all(not task["completed"] for task in progress.values())

    cancellation_target = next(item for item in shipments if item["recipient_name"] == "Иванов Иван Иванович")
    assert client.post(f"/shipments/{cancellation_target['shipment_id']}/cancel", headers=headers).status_code == 200

    tracking_target = next(item for item in shipments if item["recipient_name"] == "Петров Пётр Петрович")
    assert client.get(f"/shipments/{tracking_target['shipment_id']}", headers=headers).status_code == 200
    assert client.get(f"/shipments/{tracking_target['shipment_id']}/tracking", headers=headers).status_code == 200

    update_target = next(item for item in shipments if item["recipient_name"] == "Сидоров Сидор Сидорович")
    assert client.patch(
        f"/shipments/{update_target['shipment_id']}", headers=headers,
        json={"delivery_method": "pickup_point", "pickup_point_id": "cheb-003"},
    ).status_code == 200
    assert client.post(
        "/shipments", headers=headers,
        json={"recipient_name": "Новый Клиент", "delivery_method": "pickup_point", "pickup_point_id": "cheb-002"},
    ).status_code == 201

    final = {task["task_code"]: task for task in client.get("/progress", headers=headers).json()}
    assert all(task["completed"] for task in final.values())


def test_expired_session_cannot_continue_on_authenticated_routes(tmp_path):
    now = [datetime(2026, 1, 1, tzinfo=UTC)]
    client = TestClient(create_app(tmp_path / "delivery.sqlite3", clock=lambda: now[0]))
    token = client.post(
        "/auth/register",
        json={"surname": "Тестов", "first_name": "Тест", "group_name": "23-ИС-1"},
    ).json()["access_token"]
    headers = _headers(token)
    now[0] += timedelta(hours=24)

    responses = [
        client.get("/me", headers=headers),
        client.get("/progress", headers=headers),
        client.get("/pickup-points", headers=headers),
        client.get("/shipments", headers=headers),
    ]

    assert [response.status_code for response in responses] == [401, 401, 401, 401]
