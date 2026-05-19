from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import Shift, ShiftStatus, TimeOffRequest, TimeOffStatus, User, UserRole
from app.schemas import DashboardStats

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def _this_week_bounds():
    now = datetime.now(timezone.utc)
    start = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    return start, start + timedelta(weeks=1)


@router.get("/stats", response_model=DashboardStats)
def dashboard_stats(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    now = datetime.now(timezone.utc)
    week_start, week_end = _this_week_bounds()

    if current_user.role == UserRole.manager:
        upcoming = db.query(func.count(Shift.id)).filter(
            Shift.status == ShiftStatus.scheduled,
            Shift.start_time >= now,
        ).scalar() or 0

        week_shifts = db.query(Shift).filter(
            Shift.status.in_([ShiftStatus.scheduled, ShiftStatus.completed]),
            Shift.start_time >= week_start,
            Shift.start_time < week_end,
        ).all()

        pending_time_off = db.query(func.count(TimeOffRequest.id)).filter(
            TimeOffRequest.status == TimeOffStatus.pending,
        ).scalar() or 0

        active_employees = db.query(func.count(User.id)).filter(
            User.role == UserRole.employee,
            User.is_active == True,  # noqa: E712
        ).scalar() or 0

    else:
        upcoming = db.query(func.count(Shift.id)).filter(
            Shift.user_id == current_user.id,
            Shift.status == ShiftStatus.scheduled,
            Shift.start_time >= now,
        ).scalar() or 0

        week_shifts = db.query(Shift).filter(
            Shift.user_id == current_user.id,
            Shift.status.in_([ShiftStatus.scheduled, ShiftStatus.completed]),
            Shift.start_time >= week_start,
            Shift.start_time < week_end,
        ).all()

        pending_time_off = db.query(func.count(TimeOffRequest.id)).filter(
            TimeOffRequest.user_id == current_user.id,
            TimeOffRequest.status == TimeOffStatus.pending,
        ).scalar() or 0

        active_employees = None

    this_week_hours = round(
        sum((s.end_time - s.start_time).total_seconds() / 3600 for s in week_shifts), 1
    )

    return DashboardStats(
        upcoming_shifts=upcoming,
        this_week_shifts=len(week_shifts),
        this_week_hours=this_week_hours,
        pending_time_off=pending_time_off,
        active_employees=active_employees,
    )
