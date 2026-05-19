from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_manager
from app.database import get_db
from app.models import Availability, User
from app.schemas import AvailabilityCreate, AvailabilityOut

router = APIRouter(tags=["availability"])


@router.get("/availability/me", response_model=list[AvailabilityOut])
def my_availability(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return db.query(Availability).filter(Availability.user_id == current_user.id).all()


@router.post("/availability", response_model=AvailabilityOut, status_code=status.HTTP_201_CREATED)
def set_availability(
    payload: AvailabilityCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    slot = Availability(
        user_id=current_user.id,
        day_of_week=payload.day_of_week,
        start_time=payload.start_time,
        end_time=payload.end_time,
    )
    db.add(slot)
    db.commit()
    db.refresh(slot)
    return slot


@router.delete("/availability/{availability_id}", response_model=AvailabilityOut)
def delete_availability(
    availability_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    slot = db.query(Availability).filter(Availability.id == availability_id).first()
    if not slot:
        raise HTTPException(status_code=404, detail="Availability slot not found")
    if slot.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Cannot delete another user's availability")
    db.delete(slot)
    db.commit()
    return slot


@router.get("/employees/{employee_id}/availability", response_model=list[AvailabilityOut])
def employee_availability(
    employee_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_manager),
):
    return db.query(Availability).filter(Availability.user_id == employee_id).all()
