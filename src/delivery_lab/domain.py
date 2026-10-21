from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

ShipmentStatus = Literal["created", "accepted", "in_transit", "delivered", "cancelled"]
DeliveryMethod = Literal["courier", "pickup_point"]


@dataclass(frozen=True)
class Session:
    session_id: str
    surname: str
    first_name: str
    group_name: str
    issued_at: datetime
    expires_at: datetime


@dataclass(frozen=True)
class PickupPoint:
    pickup_point_id: str
    city: str
    address: str


@dataclass(frozen=True)
class Shipment:
    shipment_id: str
    session_id: str
    recipient_name: str
    delivery_method: DeliveryMethod
    pickup_point_id: str | None
    delivery_address: str | None
    status: ShipmentStatus
    created_at: datetime


@dataclass(frozen=True)
class TaskProgress:
    task_code: str
    title: str
    description: str
    completed: bool
