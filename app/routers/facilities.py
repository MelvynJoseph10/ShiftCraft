from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_manager
from app.database import get_db
from app.models import Facility, Shift, ShiftStatus, User
from app.schemas import FacilityCreate, FacilityOut, FacilityUpdate

router = APIRouter(prefix="/facilities", tags=["facilities"])


@router.get("", response_model=list[FacilityOut])
def list_facilities(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return db.query(Facility).all()


@router.post("", response_model=FacilityOut, status_code=status.HTTP_201_CREATED)
def create_facility(payload: FacilityCreate, db: Session = Depends(get_db), _: User = Depends(require_manager)):
    if payload.closing_time <= payload.opening_time:
        raise HTTPException(status_code=422, detail="closing_time must be after opening_time")
    facility = Facility(
        name=payload.name,
        opening_time=payload.opening_time,
        closing_time=payload.closing_time,
    )
    db.add(facility)
    db.commit()
    db.refresh(facility)
    return facility


@router.get("/{facility_id}", response_model=FacilityOut)
def get_facility(facility_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    facility = db.query(Facility).filter(Facility.id == facility_id).first()
    if not facility:
        raise HTTPException(status_code=404, detail="Facility not found")
    return facility


@router.put("/{facility_id}", response_model=FacilityOut)
def update_facility(
    facility_id: int,
    payload: FacilityUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_manager),
):
    facility = db.query(Facility).filter(Facility.id == facility_id).first()
    if not facility:
        raise HTTPException(status_code=404, detail="Facility not found")
    if payload.name is not None:
        facility.name = payload.name
    if payload.opening_time is not None:
        facility.opening_time = payload.opening_time
    if payload.closing_time is not None:
        facility.closing_time = payload.closing_time
    opening = facility.opening_time
    closing = facility.closing_time
    if closing <= opening:
        raise HTTPException(status_code=422, detail="closing_time must be after opening_time")
    db.commit()
    db.refresh(facility)
    return facility


@router.delete("/{facility_id}", response_model=FacilityOut)
def delete_facility(facility_id: int, db: Session = Depends(get_db), _: User = Depends(require_manager)):
    facility = db.query(Facility).filter(Facility.id == facility_id).first()
    if not facility:
        raise HTTPException(status_code=404, detail="Facility not found")
    upcoming = db.query(Shift).filter(
        Shift.facility_id == facility_id,
        Shift.status == ShiftStatus.scheduled,
        Shift.start_time >= datetime.now(timezone.utc),
    ).first()
    if upcoming:
        raise HTTPException(status_code=400, detail="Cannot delete a facility that has upcoming scheduled shifts")
    db.delete(facility)
    db.commit()
    return facility
