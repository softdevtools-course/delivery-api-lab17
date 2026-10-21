from __future__ import annotations

from datetime import UTC, datetime, timedelta
import sqlite3
import uuid


def iso_utc(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat()


TASK_DEFINITIONS = (
    (
        "cancel_shipment",
        "Отменить отправление",
        "Иванов Иван Иванович отказался от посылки в ПВЗ на ул. Гузовского, 16. Найдите и отмените это отправление.",
    ),
    (
        "inspect_tracking",
        "Посмотреть состояние и отслеживание",
        "Узнайте, где сейчас находится отправление Петрова Петра Петровича и какой статус был последним.",
    ),
    (
        "update_delivery",
        "Изменить доставку",
        "Сидоров Сидор Сидорович просит перенаправить посылку в ПВЗ на ул. Ленинского комсомола, 23к3. Измените доставку и проверьте новый пункт.",
    ),
    (
        "create_shipment",
        "Создать отправление в ПВЗ",
        "Оформите новую посылку для нового клиента с доставкой в ПВЗ на ул. Водопроводная, 22 и проверьте, что отправление появилось в списке.",
    ),
)


def seed_session(connection: sqlite3.Connection, session_id: str, now: datetime) -> None:
    shipments = (
        ("Иванов Иван Иванович", "pickup_point", "cheb-001", None, "accepted"),
        ("Петров Пётр Петрович", "pickup_point", "cheb-002", None, "in_transit"),
        ("Сидоров Сидор Сидорович", "pickup_point", "cheb-002", None, "accepted"),
    )
    shipment_ids: dict[str, str] = {}
    for code, recipient, method, point_id, address, status in (
        ("cancel_shipment", shipments[0][0], shipments[0][1], shipments[0][2], shipments[0][3], shipments[0][4]),
        ("inspect_tracking", shipments[1][0], shipments[1][1], shipments[1][2], shipments[1][3], shipments[1][4]),
        ("update_delivery", shipments[2][0], shipments[2][1], shipments[2][2], shipments[2][3], shipments[2][4]),
    ):
        shipment_id = str(uuid.uuid4())
        shipment_ids[code] = shipment_id
        created_at = now - timedelta(hours=2)
        connection.execute(
            """INSERT INTO shipments
               (shipment_id, session_id, recipient_name, delivery_method,
                pickup_point_id, delivery_address, status, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (shipment_id, session_id, recipient, method, point_id, address, status, iso_utc(created_at)),
        )
        event_statuses = ("created", "accepted")
        if status == "in_transit":
            event_statuses += ("in_transit",)
        for index, event_status in enumerate(event_statuses):
            occurred_at = created_at + timedelta(minutes=30 * index)
            description = {
                "created": "Отправление создано",
                "accepted": "Отправление принято к обработке",
                "in_transit": "Отправление в пути",
            }[event_status]
            connection.execute(
                """INSERT INTO tracking_events
                   (event_id, shipment_id, status, description, occurred_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (str(uuid.uuid4()), shipment_id, event_status, description, iso_utc(occurred_at)),
            )

    for code, title, description in TASK_DEFINITIONS:
        connection.execute(
            """INSERT INTO tasks
               (task_id, session_id, task_code, target_shipment_id,
                expected_pickup_point_id, created_after)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                str(uuid.uuid4()),
                session_id,
                code,
                shipment_ids.get(code),
                "cheb-003" if code == "update_delivery" else "cheb-002" if code == "create_shipment" else None,
                iso_utc(now),
            ),
        )
