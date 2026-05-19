import csv
import io
from collections import defaultdict
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.auth import require_manager
from app.database import get_db
from app.models import Shift, ShiftStatus, User, UserRole
from app.routers.schedules import _week_bounds
from app.schemas import EmployeeHoursOut

router = APIRouter(prefix="/reports", tags=["reports"])


def _current_iso_week() -> str:
    now = datetime.now(timezone.utc)
    return f"{now.isocalendar().year}-W{now.isocalendar().week:02d}"


@router.get("/hours", response_model=list[EmployeeHoursOut])
def hours_report(
    week: str = Query(None, description="ISO week YYYY-WW, defaults to current week"),
    db: Session = Depends(get_db),
    _: User = Depends(require_manager),
):
    _, rows = _build_hours_data(week, db)
    return [
        EmployeeHoursOut(
            employee_id=r["employee_id"],
            employee_name=r["employee"],
            scheduled_hours=r["scheduled_hours"],
            completed_hours=r["completed_hours"],
            total_shifts=r["total_shifts"],
        )
        for r in rows
    ]


def _build_hours_data(week: str | None, db: Session):
    week_str = week or _current_iso_week()
    week_start, week_end = _week_bounds(week_str)
    employees = (
        db.query(User)
        .filter(User.role == UserRole.employee, User.is_active == True)  # noqa: E712
        .order_by(User.name)
        .all()
    )
    emp_ids = [e.id for e in employees]
    week_shifts = db.query(Shift).filter(
        Shift.user_id.in_(emp_ids),
        Shift.start_time >= week_start,
        Shift.start_time < week_end,
        Shift.status.in_([ShiftStatus.scheduled, ShiftStatus.completed]),
    ).all()
    shifts_by_emp = defaultdict(list)
    for s in week_shifts:
        shifts_by_emp[s.user_id].append(s)
    rows = []
    for emp in employees:
        emp_shifts = shifts_by_emp[emp.id]
        rows.append({
            "employee_id": emp.id,
            "employee": emp.name,
            "scheduled_hours": round(sum((s.end_time - s.start_time).total_seconds() / 3600 for s in emp_shifts if s.status == ShiftStatus.scheduled), 1),
            "completed_hours": round(sum((s.end_time - s.start_time).total_seconds() / 3600 for s in emp_shifts if s.status == ShiftStatus.completed), 1),
            "total_shifts": len(emp_shifts),
        })
    return week_str, rows


@router.get("/hours/export")
def hours_export(
    week: str = Query(None),
    db: Session = Depends(get_db),
    _: User = Depends(require_manager),
):
    week_str, rows = _build_hours_data(week, db)
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=["employee", "scheduled_hours", "completed_hours", "total_shifts"])
    writer.writeheader()
    writer.writerows(rows)
    buf.seek(0)
    filename = f"shiftcraft-hours-{week_str}.csv"
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
