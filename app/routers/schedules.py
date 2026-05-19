from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_manager, send_shift_assigned_email, send_shift_cancelled_email
from app.database import get_db
from app.models import Facility, Shift, ShiftStatus, User
from app.schemas import ShiftCreate, ShiftOut

router = APIRouter(tags=["schedules"])


def _week_bounds(week_str: str):
    """Parse YYYY-WW into (start_datetime, end_datetime) in UTC."""
    year, week = map(int, week_str.split("-W"))
    # ISO week: Monday is day 1
    start = datetime.fromisocalendar(year, week, 1).replace(tzinfo=timezone.utc)
    end = start + timedelta(weeks=1)
    return start, end


@router.post("/schedules", response_model=ShiftOut, status_code=status.HTTP_201_CREATED)
def create_shift(payload: ShiftCreate, db: Session = Depends(get_db), _: User = Depends(require_manager)):
    if payload.end_time <= payload.start_time:
        raise HTTPException(status_code=422, detail="Shift end time must be after start time")
    employee = db.query(User).filter(User.id == payload.user_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    if not employee.is_active:
        raise HTTPException(status_code=400, detail="Cannot assign shift to inactive employee")
    conflict = db.query(Shift).filter(
        Shift.user_id == payload.user_id,
        Shift.status == ShiftStatus.scheduled,
        Shift.start_time < payload.end_time,
        Shift.end_time > payload.start_time,
    ).first()
    if conflict:
        raise HTTPException(
            status_code=409,
            detail=f"Employee already has a scheduled shift from {conflict.start_time.strftime('%b %d, %H:%M')} to {conflict.end_time.strftime('%H:%M')}",
        )
    shift = Shift(
        facility_id=payload.facility_id,
        user_id=payload.user_id,
        start_time=payload.start_time,
        end_time=payload.end_time,
    )
    db.add(shift)
    db.commit()
    db.refresh(shift)
    facility = db.query(Facility).filter(Facility.id == payload.facility_id).first()
    send_shift_assigned_email(
        employee.email,
        employee.name,
        facility.name if facility else f"Facility #{payload.facility_id}",
        shift.start_time,
        shift.end_time,
    )
    return shift


@router.get("/schedules", response_model=list[ShiftOut])
def list_shifts(
    week: str = Query(None, description="ISO week filter YYYY-WW, e.g. 2024-W01"),
    db: Session = Depends(get_db),
    _: User = Depends(require_manager),
):
    query = db.query(Shift)
    if week:
        start, end = _week_bounds(week)
        query = query.filter(Shift.start_time >= start, Shift.start_time < end)
    return query.all()


@router.get("/employees/{employee_id}/schedule", response_model=list[ShiftOut])
def employee_schedule(
    employee_id: int,
    week: str = Query(None, description="ISO week filter YYYY-WW"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "manager" and current_user.id != employee_id:
        raise HTTPException(status_code=403, detail="Access denied")
    query = db.query(Shift).filter(Shift.user_id == employee_id)
    if week:
        start, end = _week_bounds(week)
        query = query.filter(Shift.start_time >= start, Shift.start_time < end)
    return query.all()


@router.put("/schedules/{shift_id}/complete", response_model=ShiftOut)
def complete_shift(shift_id: int, db: Session = Depends(get_db), _: User = Depends(require_manager)):
    shift = db.query(Shift).filter(Shift.id == shift_id).first()
    if not shift:
        raise HTTPException(status_code=404, detail="Shift not found")
    if shift.status != ShiftStatus.scheduled:
        raise HTTPException(status_code=400, detail="Only scheduled shifts can be marked as completed")
    if shift.end_time.replace(tzinfo=timezone.utc) > datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Cannot complete a shift that hasn't ended yet")
    shift.status = ShiftStatus.completed
    db.commit()
    db.refresh(shift)
    return shift


@router.delete("/schedules/{shift_id}", response_model=ShiftOut)
def cancel_shift(shift_id: int, db: Session = Depends(get_db), _: User = Depends(require_manager)):
    shift = db.query(Shift).filter(Shift.id == shift_id).first()
    if not shift:
        raise HTTPException(status_code=404, detail="Shift not found")
    if shift.status != ShiftStatus.scheduled:
        raise HTTPException(status_code=400, detail="Only scheduled shifts can be cancelled")
    employee = db.query(User).filter(User.id == shift.user_id).first()
    facility = db.query(Facility).filter(Facility.id == shift.facility_id).first()
    shift.status = ShiftStatus.cancelled
    db.commit()
    db.refresh(shift)
    if employee:
        send_shift_cancelled_email(
            employee.email,
            employee.name,
            facility.name if facility else f"Facility #{shift.facility_id}",
            shift.start_time,
            shift.end_time,
        )
    return shift
