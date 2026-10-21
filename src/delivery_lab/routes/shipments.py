from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Path, Request, status
from pydantic import BaseModel, Field, StringConstraints, model_validator

from delivery_lab.auth import authenticated_session
from delivery_lab.domain import Session
from delivery_lab.shipment_service import (
    cancel_shipment as cancel_shipment_service,
    create_shipment as create_shipment_service,
    get_shipment,
    get_tracking,
    list_shipments,
    shipment_dict,
    update_shipment as update_shipment_service,
)

router = APIRouter(prefix="/shipments", tags=["Отправления"])
RecipientName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=120)]
DeliveryAddress = Annotated[str, StringConstraints(strip_whitespace=True, min_length=5, max_length=240)]
ShipmentId = Annotated[str, Path(min_length=36, max_length=36)]


class ShipmentCreate(BaseModel):
    recipient_name: RecipientName
    delivery_method: Literal["courier", "pickup_point"]
    pickup_point_id: str | None = None
    delivery_address: DeliveryAddress | None = None

    @model_validator(mode="after")
    def validate_destination(self) -> ShipmentCreate:
        if self.delivery_method == "pickup_point" and (not self.pickup_point_id or self.delivery_address is not None):
            raise ValueError("pickup_point delivery requires only pickup_point_id")
        if self.delivery_method == "courier" and (not self.delivery_address or self.pickup_point_id is not None):
            raise ValueError("courier delivery requires only delivery_address")
        return self


class ShipmentUpdate(BaseModel):
    delivery_method: Literal["courier", "pickup_point"] | None = None
    pickup_point_id: str | None = None
    delivery_address: DeliveryAddress | None = None

    @model_validator(mode="after")
    def validate_destination(self) -> ShipmentUpdate:
        if self.delivery_method is None and self.pickup_point_id is not None and self.delivery_address is not None:
            raise ValueError("Provide either pickup_point_id or delivery_address")
        if self.delivery_method == "pickup_point" and (not self.pickup_point_id or self.delivery_address is not None):
            raise ValueError("pickup_point delivery requires only pickup_point_id")
        if self.delivery_method == "courier" and (not self.delivery_address or self.pickup_point_id is not None):
            raise ValueError("courier delivery requires only delivery_address")
        if self.delivery_method is None and not self.model_fields_set.intersection({"pickup_point_id", "delivery_address"}):
            raise ValueError("At least one delivery field is required")
        return self


@router.get("")
def shipments(request: Request, session: Session = Depends(authenticated_session)) -> list[dict]:
    return [shipment_dict(item) for item in list_shipments(request.app.state.database_path, session)]


@router.post("", status_code=status.HTTP_201_CREATED, responses={201: {"description": "Created shipment"}})
def create_shipment(
    payload: ShipmentCreate,
    request: Request,
    session: Session = Depends(authenticated_session),
) -> dict:
    shipment = create_shipment_service(
        request.app.state.database_path,
        session,
        payload.recipient_name,
        payload.delivery_method,
        payload.pickup_point_id,
        payload.delivery_address,
        request.app.state.clock(),
    )
    request.state.resource_id = shipment.shipment_id
    return shipment_dict(shipment)


@router.get("/{shipment_id}")
def shipment_detail(
    shipment_id: ShipmentId,
    request: Request,
    session: Session = Depends(authenticated_session),
) -> dict:
    request.state.resource_id = shipment_id
    return shipment_dict(get_shipment(request.app.state.database_path, session, shipment_id))


@router.patch("/{shipment_id}")
def update_shipment(
    shipment_id: ShipmentId,
    payload: ShipmentUpdate,
    request: Request,
    session: Session = Depends(authenticated_session),
) -> dict:
    request.state.resource_id = shipment_id
    shipment = update_shipment_service(
        request.app.state.database_path,
        session,
        shipment_id,
        payload.delivery_method,
        payload.pickup_point_id,
        payload.delivery_address,
        request.app.state.clock(),
    )
    return shipment_dict(shipment)


@router.post("/{shipment_id}/cancel")
def cancel_shipment(
    shipment_id: ShipmentId,
    request: Request,
    session: Session = Depends(authenticated_session),
) -> dict:
    request.state.resource_id = shipment_id
    shipment = cancel_shipment_service(
        request.app.state.database_path, session, shipment_id, request.app.state.clock()
    )
    return shipment_dict(shipment)


@router.get("/{shipment_id}/tracking")
def tracking(
    shipment_id: ShipmentId,
    request: Request,
    session: Session = Depends(authenticated_session),
) -> list[dict[str, str]]:
    request.state.resource_id = shipment_id
    return get_tracking(request.app.state.database_path, session, shipment_id)
