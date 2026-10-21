from __future__ import annotations

from pathlib import Path
import sqlite3

from delivery_lab.database import get_connection
from delivery_lab.domain import Session, TaskProgress
from delivery_lab.seed import TASK_DEFINITIONS


def _completed(
    connection: sqlite3.Connection,
    session: Session,
    task_code: str,
    target_shipment_id: str | None,
    expected_pickup_point_id: str | None,
    created_after: str,
) -> bool:
    if task_code == "cancel_shipment" and target_shipment_id:
        row = connection.execute(
            "SELECT status FROM shipments WHERE shipment_id = ? AND session_id = ?",
            (target_shipment_id, session.session_id),
        ).fetchone()
        return row is not None and row["status"] == "cancelled"

    if task_code == "inspect_tracking" and target_shipment_id:
        detail_read = connection.execute(
            """SELECT 1 FROM audit_log
               WHERE session_id = ? AND method = 'GET' AND status_code = 200
                 AND ((route = '/shipments' AND resource_id IS NULL)
                   OR (route = '/shipments/{shipment_id}' AND resource_id = ?))
               LIMIT 1""",
            (session.session_id, target_shipment_id),
        ).fetchone()
        tracking_read = connection.execute(
            """SELECT 1 FROM audit_log
               WHERE session_id = ? AND method = 'GET' AND status_code = 200
                 AND route = '/shipments/{shipment_id}/tracking' AND resource_id = ?
               LIMIT 1""",
            (session.session_id, target_shipment_id),
        ).fetchone()
        return detail_read is not None and tracking_read is not None

    if task_code == "update_delivery" and target_shipment_id and expected_pickup_point_id:
        row = connection.execute(
            """SELECT delivery_method, pickup_point_id FROM shipments
               WHERE shipment_id = ? AND session_id = ?""",
            (target_shipment_id, session.session_id),
        ).fetchone()
        return (
            row is not None
            and row["delivery_method"] == "pickup_point"
            and row["pickup_point_id"] == expected_pickup_point_id
        )

    if task_code == "create_shipment" and expected_pickup_point_id:
        row = connection.execute(
            """SELECT 1 FROM shipments
               WHERE session_id = ? AND delivery_method = 'pickup_point'
                 AND pickup_point_id = ? AND created_at >= ?
               LIMIT 1""",
            (session.session_id, expected_pickup_point_id, created_after),
        ).fetchone()
        return row is not None

    return False


def get_progress(database_path: str | Path, session: Session) -> list[TaskProgress]:
    with get_connection(database_path) as connection:
        rows = connection.execute(
            """SELECT task_code, target_shipment_id, expected_pickup_point_id, created_after
               FROM tasks WHERE session_id = ? ORDER BY task_id""",
            (session.session_id,),
        ).fetchall()
        by_code = {row["task_code"]: row for row in rows}
        progress: list[TaskProgress] = []
        for task_code, title, description in TASK_DEFINITIONS:
            row = by_code.get(task_code)
            complete = False
            if row is not None:
                complete = _completed(
                    connection,
                    session,
                    task_code,
                    row["target_shipment_id"],
                    row["expected_pickup_point_id"],
                    row["created_after"],
                )
            progress.append(TaskProgress(task_code, title, description, complete))
    return progress


def progress_dict(item: TaskProgress) -> dict[str, str | bool]:
    return {
        "task_code": item.task_code,
        "title": item.title,
        "description": item.description,
        "completed": item.completed,
    }
