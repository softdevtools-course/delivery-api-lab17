from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
import sqlite3
import uuid

from fastapi import HTTPException

from delivery_lab.database import get_connection
from delivery_lab.domain import PickupPoint, Session, Shipment, ShipmentStatus
from delivery_lab.seed import iso_utc


def shipment_from_row(row: sqlite3.Row) -> Shipment:
    return Shipment(
        shipment_id=row["shipment_id"],
        session_id=row["session_id"],
        recipient_name=row["recipient_name"],
        delivery_method=row["delivery_method"],
        pickup_point_id=row["pickup_point_id"],
        delivery_address=row["delivery_address"],
        status=row["status"],
        created_at=datetime.fromisoformat(row["created_at"]),
    )


def shipment_dict(shipment: Shipment) -> dict[str, str | None]:
    return {
        "shipment_id": shipment.shipment_id,
        "recipient_name": shipment.recipient_name,
        "delivery_method": shipment.delivery_method,
        "pickup_point_id": shipment.pickup_point_id,
        "delivery_address": shipment.delivery_address,
        "status": shipment.status,
        "created_at": shipment.created_at.isoformat(),
    }


def get_pickup_points(database_path: str | Path) -> list[PickupPoint]:
    with get_connection(database_path) as connection:
        rows = connection.execute(
            "SELECT pickup_point_id, city, address FROM pickup_points ORDER BY pickup_point_id"
        ).fetchall()
    return [PickupPoint(row["pickup_point_id"], row["city"], row["address"]) for row in rows]


def list_shipments(database_path: str | Path, session: Session) -> list[Shipment]:
    with get_connection(database_path) as connection:
        rows = connection.execute(
            "SELECT * FROM shipments WHERE session_id = ? ORDER BY created_at, shipment_id",
            (session.session_id,),
        ).fetchall()
    return [shipment_from_row(row) for row in rows]


def get_shipment(database_path: str | Path, session: Session, shipment_id: str) -> Shipment:
    with get_connection(database_path) as connection:
        row = connection.execute(
            "SELECT * FROM shipments WHERE shipment_id = ? AND session_id = ?",
            (shipment_id, session.session_id),
        ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Shipment not found")
    return shipment_from_row(row)


def _validate_pickup_point(connection: sqlite3.Connection, pickup_point_id: str) -> None:
    row = connection.execute(
        "SELECT 1 FROM pickup_points WHERE pickup_point_id = ?", (pickup_point_id,)
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=422, detail="Unknown pickup point")


def create_shipment(
    database_path: str | Path,
    session: Session,
    recipient_name: str,
    delivery_method: str,
    pickup_point_id: str | None,
    delivery_address: str | None,
    now: datetime,
) -> Shipment:
    created_at = now.astimezone(UTC) if now.tzinfo else now.replace(tzinfo=UTC)
    if delivery_method == "pickup_point":
        if not pickup_point_id or delivery_address is not None:
            raise HTTPException(status_code=422, detail="Pickup-point delivery requires only a pickup point ID")
    elif delivery_method == "courier":
        if not delivery_address or pickup_point_id is not None:
            raise HTTPException(status_code=422, detail="Courier delivery requires only a delivery address")
    else:
        raise HTTPException(status_code=422, detail="Unknown delivery method")

    shipment = Shipment(
        shipment_id=str(uuid.uuid4()),
        session_id=session.session_id,
        recipient_name=recipient_name,
        delivery_method=delivery_method,
        pickup_point_id=pickup_point_id,
        delivery_address=delivery_address,
        status="created",
        created_at=created_at,
    )
    with get_connection(database_path) as connection:
        if pickup_point_id:
            _validate_pickup_point(connection, pickup_point_id)
        connection.execute(
            """INSERT INTO shipments
               (shipment_id, session_id, recipient_name, delivery_method,
                pickup_point_id, delivery_address, status, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                shipment.shipment_id,
                session.session_id,
                shipment.recipient_name,
                shipment.delivery_method,
                shipment.pickup_point_id,
                shipment.delivery_address,
                shipment.status,
                iso_utc(created_at),
            ),
        )
        connection.execute(
            """INSERT INTO tracking_events
               (event_id, shipment_id, status, description, occurred_at)
               VALUES (?, ?, 'created', ?, ?)""",
            (str(uuid.uuid4()), shipment.shipment_id, "Отправление создано", iso_utc(created_at)),
        )
    return shipment


def update_shipment(
    database_path: str | Path,
    session: Session,
    shipment_id: str,
    delivery_method: str | None,
    pickup_point_id: str | None,
    delivery_address: str | None,
    now: datetime,
) -> Shipment:
    with get_connection(database_path) as connection:
        row = connection.execute(
            "SELECT * FROM shipments WHERE shipment_id = ? AND session_id = ?",
            (shipment_id, session.session_id),
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Shipment not found")
        if row["status"] not in ("created", "accepted"):
            raise HTTPException(status_code=409, detail="Shipment can no longer be changed")

        method = delivery_method or (
            "pickup_point" if pickup_point_id is not None else
            "courier" if delivery_address is not None else
            row["delivery_method"]
        )
        point_id = None
        address = None
        if method == "pickup_point":
            point_id = pickup_point_id
            if point_id is None and row["delivery_method"] == "pickup_point":
                point_id = row["pickup_point_id"]
            if not point_id or address is not None:
                raise HTTPException(status_code=422, detail="Pickup-point delivery requires only a pickup point ID")
            _validate_pickup_point(connection, point_id)
        else:
            address = delivery_address
            if address is None and row["delivery_method"] == "courier":
                address = row["delivery_address"]
            if not address or point_id is not None:
                raise HTTPException(status_code=422, detail="Courier delivery requires only a delivery address")

        connection.execute(
            """UPDATE shipments SET delivery_method = ?, pickup_point_id = ?, delivery_address = ?
               WHERE shipment_id = ? AND session_id = ?""",
            (method, point_id, address, shipment_id, session.session_id),
        )
        result = connection.execute(
            "SELECT * FROM shipments WHERE shipment_id = ? AND session_id = ?",
            (shipment_id, session.session_id),
        ).fetchone()
    return shipment_from_row(result)


def cancel_shipment(
    database_path: str | Path, session: Session, shipment_id: str, now: datetime
) -> Shipment:
    occurred_at = now.astimezone(UTC) if now.tzinfo else now.replace(tzinfo=UTC)
    with get_connection(database_path) as connection:
        row = connection.execute(
            "SELECT * FROM shipments WHERE shipment_id = ? AND session_id = ?",
            (shipment_id, session.session_id),
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Shipment not found")
        if row["status"] not in ("created", "accepted"):
            raise HTTPException(status_code=409, detail="Shipment can no longer be cancelled")
        connection.execute(
            "UPDATE shipments SET status = 'cancelled' WHERE shipment_id = ? AND session_id = ?",
            (shipment_id, session.session_id),
        )
        connection.execute(
            """INSERT INTO tracking_events
               (event_id, shipment_id, status, description, occurred_at)
               VALUES (?, ?, 'cancelled', ?, ?)""",
            (str(uuid.uuid4()), shipment_id, "Отправление отменено", iso_utc(occurred_at)),
        )
        result = connection.execute(
            "SELECT * FROM shipments WHERE shipment_id = ? AND session_id = ?",
            (shipment_id, session.session_id),
        ).fetchone()
    return shipment_from_row(result)


def get_tracking(database_path: str | Path, session: Session, shipment_id: str) -> list[dict[str, str]]:
    with get_connection(database_path) as connection:
        shipment = connection.execute(
            "SELECT 1 FROM shipments WHERE shipment_id = ? AND session_id = ?",
            (shipment_id, session.session_id),
        ).fetchone()
        if shipment is None:
            raise HTTPException(status_code=404, detail="Shipment not found")
        rows = connection.execute(
            "SELECT status, description, occurred_at FROM tracking_events WHERE shipment_id = ? ORDER BY occurred_at, event_id",
            (shipment_id,),
        ).fetchall()
    return [
        {"status": row["status"], "description": row["description"], "occurred_at": row["occurred_at"]}
        for row in rows
    ]
