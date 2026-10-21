from fastapi.testclient import TestClient

from delivery_lab.main import create_app


def register(client: TestClient, surname: str = "Иванов") -> str:
    response = client.post(
        "/auth/register",
        json={"surname": surname, "first_name": "Иван", "group_name": "23-ИС-1"},
    )
    assert response.status_code == 201
    return response.json()["access_token"]


def headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_pickup_points_list_has_cheboksary_addresses(tmp_path):
    client = TestClient(create_app(tmp_path / "delivery.sqlite3"))
    token = register(client)

    response = client.get("/pickup-points", headers=headers(token))

    assert response.status_code == 200
    assert {item["address"] for item in response.json()} == {
        "ул. Гузовского, 16",
        "ул. Водопроводная, 22",
        "ул. Ленинского комсомола, 23к3",
    }
    assert {item["city"] for item in response.json()} == {"Чебоксары"}


def test_student_only_sees_own_shipments(tmp_path):
    client = TestClient(create_app(tmp_path / "delivery.sqlite3"))
    first = register(client, "Иванов")
    second = register(client, "Петров")

    first_shipments = client.get("/shipments", headers=headers(first)).json()
    second_shipments = client.get("/shipments", headers=headers(second)).json()

    first_ids = {item["shipment_id"] for item in first_shipments}
    second_ids = {item["shipment_id"] for item in second_shipments}
    assert len(first_ids) == len(second_ids) == 3
    assert first_ids.isdisjoint(second_ids)


def test_foreign_shipment_id_returns_not_found(tmp_path):
    client = TestClient(create_app(tmp_path / "delivery.sqlite3"))
    first = register(client, "Иванов")
    second = register(client, "Петров")
    shipment_id = client.get("/shipments", headers=headers(first)).json()[0]["shipment_id"]

    response = client.get(f"/shipments/{shipment_id}", headers=headers(second))

    assert response.status_code == 404
    assert response.json()["detail"] == "Shipment not found"


def test_cancel_changes_only_target_shipment_status(tmp_path):
    client = TestClient(create_app(tmp_path / "delivery.sqlite3"))
    token = register(client)
    shipments = client.get("/shipments", headers=headers(token)).json()
    target = next(item for item in shipments if item["recipient_name"] == "Иванов Иван Иванович")

    response = client.post(f"/shipments/{target['shipment_id']}/cancel", headers=headers(token))

    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"
    other = client.get("/shipments", headers=headers(token)).json()
    assert next(item for item in other if item["shipment_id"] != target["shipment_id"])["status"] != "cancelled"


def test_update_changes_delivery_to_requested_pickup_point(tmp_path):
    client = TestClient(create_app(tmp_path / "delivery.sqlite3"))
    token = register(client)
    shipments = client.get("/shipments", headers=headers(token)).json()
    target = next(item for item in shipments if item["recipient_name"] == "Сидоров Сидор Сидорович")

    response = client.patch(
        f"/shipments/{target['shipment_id']}",
        headers=headers(token),
        json={"delivery_method": "pickup_point", "pickup_point_id": "cheb-003"},
    )

    assert response.status_code == 200
    assert response.json()["pickup_point_id"] == "cheb-003"
    assert response.json()["status"] == "accepted"


def test_update_can_change_only_pickup_point_id(tmp_path):
    client = TestClient(create_app(tmp_path / "delivery.sqlite3"))
    token = register(client)
    shipments = client.get("/shipments", headers=headers(token)).json()
    target = next(item for item in shipments if item["recipient_name"] == "Сидоров Сидор Сидорович")

    response = client.patch(
        f"/shipments/{target['shipment_id']}",
        headers=headers(token),
        json={"pickup_point_id": "cheb-003"},
    )

    assert response.status_code == 200
    assert response.json()["delivery_method"] == "pickup_point"
    assert response.json()["pickup_point_id"] == "cheb-003"


def test_create_shipment_in_pickup_point(tmp_path):
    client = TestClient(create_app(tmp_path / "delivery.sqlite3"))
    token = register(client)

    response = client.post(
        "/shipments",
        headers=headers(token),
        json={
            "recipient_name": "Новый Получатель",
            "delivery_method": "pickup_point",
            "pickup_point_id": "cheb-002",
        },
    )

    assert response.status_code == 201
    assert response.json()["status"] == "created"
    assert response.json()["recipient_name"] == "Новый Получатель"
    listed = client.get("/shipments", headers=headers(token)).json()
    assert response.json()["shipment_id"] in {item["shipment_id"] for item in listed}


def test_tracking_returns_ordered_status_history(tmp_path):
    client = TestClient(create_app(tmp_path / "delivery.sqlite3"))
    token = register(client)
    shipments = client.get("/shipments", headers=headers(token)).json()
    target = next(item for item in shipments if item["recipient_name"] == "Петров Пётр Петрович")

    response = client.get(f"/shipments/{target['shipment_id']}/tracking", headers=headers(token))

    assert response.status_code == 200
    assert [item["status"] for item in response.json()] == ["created", "accepted", "in_transit"]


def test_in_transit_shipment_cannot_be_changed_or_cancelled(tmp_path):
    client = TestClient(create_app(tmp_path / "delivery.sqlite3"))
    token = register(client)
    shipments = client.get("/shipments", headers=headers(token)).json()
    target = next(item for item in shipments if item["status"] == "in_transit")

    update = client.patch(
        f"/shipments/{target['shipment_id']}",
        headers=headers(token),
        json={"delivery_method": "pickup_point", "pickup_point_id": "cheb-003"},
    )
    cancel = client.post(f"/shipments/{target['shipment_id']}/cancel", headers=headers(token))

    assert update.status_code == 409
    assert cancel.status_code == 409
