from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from delivery_lab.auth import authenticated_session
from delivery_lab.domain import Session
from delivery_lab.shipment_service import get_pickup_points

router = APIRouter()


@router.get("/pickup-points", tags=["Справочник"])
def pickup_points(request: Request, _: Session = Depends(authenticated_session)) -> list[dict[str, str]]:
    return [
        {
            "pickup_point_id": point.pickup_point_id,
            "city": point.city,
            "address": point.address,
        }
        for point in get_pickup_points(request.app.state.database_path)
    ]
