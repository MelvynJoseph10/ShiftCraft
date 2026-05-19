from collections import defaultdict
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
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

    results = []
    for emp in employees:
        emp_shifts = shifts_by_emp[emp.id]
        scheduled_h = sum(
            (s.end_time - s.start_time).total_seconds() / 3600
            for s in emp_shifts if s.status == ShiftStatus.scheduled
        )
        completed_h = sum(
            (s.end_time - s.start_time).total_seconds() / 3600
            for s in emp_shifts if s.status == ShiftStatus.completed
        )
        results.append(EmployeeHoursOut(
            employee_id=emp.id,
            employee_name=emp.name,
            scheduled_hours=round(scheduled_h, 1),
            completed_hours=round(completed_h, 1),
            total_shifts=len(emp_shifts),
        ))

    return results
