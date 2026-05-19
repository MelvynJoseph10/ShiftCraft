from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_manager, send_time_off_decision_email
from app.database import get_db
from app.models import TimeOffRequest, TimeOffStatus, User
from app.schemas import TimeOffCreate, TimeOffOut

router = APIRouter(prefix="/time-off", tags=["time-off"])


@router.post("", response_model=TimeOffOut, status_code=status.HTTP_201_CREATED)
def submit_time_off(
    payload: TimeOffCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    req = TimeOffRequest(
        user_id=current_user.id,
        start_date=payload.start_date,
        end_date=payload.end_date,
        reason=payload.reason,
    )
    db.add(req)
    db.commit()
    db.refresh(req)
    return req


@router.get("/me", response_model=list[TimeOffOut])
def my_time_off(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return (
        db.query(TimeOffRequest)
        .filter(TimeOffRequest.user_id == current_user.id)
        .order_by(TimeOffRequest.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


@router.get("", response_model=list[TimeOffOut])
def all_time_off(db: Session = Depends(get_db), _: User = Depends(require_manager)):
    return db.query(TimeOffRequest).filter(TimeOffRequest.status == TimeOffStatus.pending).all()


@router.get("/employee/{employee_id}", response_model=list[TimeOffOut])
def employee_time_off(employee_id: int, db: Session = Depends(get_db), _: User = Depends(require_manager)):
    return db.query(TimeOffRequest).filter(TimeOffRequest.user_id == employee_id).order_by(TimeOffRequest.created_at.desc()).all()


@router.put("/{request_id}/approve", response_model=TimeOffOut)
def approve_time_off(
    request_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager),
):
    req = db.query(TimeOffRequest).filter(TimeOffRequest.id == request_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
    req.status = TimeOffStatus.approved
    req.reviewed_by = current_user.id
    db.commit()
    db.refresh(req)
    send_time_off_decision_email(req.user.email, req.user.name, "approved", req.start_date, req.end_date)
    return req


@router.put("/{request_id}/deny", response_model=TimeOffOut)
def deny_time_off(
    request_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager),
):
    req = db.query(TimeOffRequest).filter(TimeOffRequest.id == request_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
    req.status = TimeOffStatus.denied
    req.reviewed_by = current_user.id
    db.commit()
    db.refresh(req)
    send_time_off_decision_email(req.user.email, req.user.name, "denied", req.start_date, req.end_date)
    return req
