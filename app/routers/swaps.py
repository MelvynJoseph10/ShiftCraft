from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth import (
    get_current_user,
    require_manager,
    send_swap_decision_email,
    send_swap_requested_email,
    send_swap_response_email,
)
from app.database import get_db
from app.models import Facility, Shift, ShiftStatus, ShiftSwapRequest, SwapStatus, User
from app.schemas import ShiftWithNamesOut, SwapRequestCreate, SwapRequestOut

router = APIRouter(prefix="/swaps", tags=["swaps"])


def _shift_label(shift: Shift, db: Session) -> str:
    fac = db.query(Facility).filter(Facility.id == shift.facility_id).first()
    fac_name = fac.name if fac else f"Facility #{shift.facility_id}"
    return f"{fac_name} on {shift.start_time.strftime('%b %d %H:%M')}–{shift.end_time.strftime('%H:%M')}"


def _build_swap_out(req: ShiftSwapRequest, db: Session) -> SwapRequestOut:
    rs = req.requester_shift
    ts = req.target_shift
    rs_fac = db.query(Facility).filter(Facility.id == rs.facility_id).first()
    ts_fac = db.query(Facility).filter(Facility.id == ts.facility_id).first()
    target_user = db.query(User).filter(User.id == ts.user_id).first()
    return SwapRequestOut(
        id=req.id,
        requester_id=req.requester_id,
        requester_name=req.requester.name,
        requester_shift_id=req.requester_shift_id,
        requester_shift_start=rs.start_time,
        requester_shift_end=rs.end_time,
        requester_facility=rs_fac.name if rs_fac else f"Facility #{rs.facility_id}",
        target_shift_id=req.target_shift_id,
        target_user_id=ts.user_id,
        target_name=target_user.name if target_user else "Unknown",
        target_shift_start=ts.start_time,
        target_shift_end=ts.end_time,
        target_facility=ts_fac.name if ts_fac else f"Facility #{ts.facility_id}",
        status=req.status,
        created_at=req.created_at,
    )


@router.get("/available-shifts", response_model=list[ShiftWithNamesOut])
def available_shifts(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    now = datetime.now(timezone.utc)
    shifts = db.query(Shift).filter(
        Shift.user_id != current_user.id,
        Shift.status == ShiftStatus.scheduled,
        Shift.start_time > now,
    ).order_by(Shift.start_time).all()

    result = []
    fac_cache, emp_cache = {}, {}
    for s in shifts:
        if s.facility_id not in fac_cache:
            fac_cache[s.facility_id] = db.query(Facility).filter(Facility.id == s.facility_id).first()
        if s.user_id not in emp_cache:
            emp_cache[s.user_id] = db.query(User).filter(User.id == s.user_id).first()
        fac = fac_cache[s.facility_id]
        emp = emp_cache[s.user_id]
        result.append(ShiftWithNamesOut(
            id=s.id,
            facility_id=s.facility_id,
            user_id=s.user_id,
            start_time=s.start_time,
            end_time=s.end_time,
            status=s.status,
            employee_name=emp.name if emp else "Unknown",
            facility_name=fac.name if fac else f"Facility #{s.facility_id}",
        ))
    return result


@router.post("", response_model=SwapRequestOut, status_code=status.HTTP_201_CREATED)
def create_swap(payload: SwapRequestCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    my_shift = db.query(Shift).filter(Shift.id == payload.requester_shift_id).first()
    if not my_shift or my_shift.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Your shift not found")
    if my_shift.status != ShiftStatus.scheduled:
        raise HTTPException(status_code=400, detail="Only scheduled shifts can be swapped")
    if my_shift.start_time.replace(tzinfo=timezone.utc) <= datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Cannot swap a shift that has already started")

    tgt_shift = db.query(Shift).filter(Shift.id == payload.target_shift_id).first()
    if not tgt_shift or tgt_shift.user_id == current_user.id:
        raise HTTPException(status_code=404, detail="Target shift not found")
    if tgt_shift.status != ShiftStatus.scheduled:
        raise HTTPException(status_code=400, detail="Target shift is not scheduled")

    existing = db.query(ShiftSwapRequest).filter(
        ShiftSwapRequest.requester_shift_id == payload.requester_shift_id,
        ShiftSwapRequest.status.in_([SwapStatus.pending, SwapStatus.accepted]),
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="A pending swap request already exists for this shift")

    req = ShiftSwapRequest(
        requester_id=current_user.id,
        requester_shift_id=payload.requester_shift_id,
        target_shift_id=payload.target_shift_id,
    )
    db.add(req)
    db.commit()
    db.refresh(req)

    target_user = db.query(User).filter(User.id == tgt_shift.user_id).first()
    if target_user:
        send_swap_requested_email(
            target_user.email, target_user.name, current_user.name,
            _shift_label(my_shift, db), _shift_label(tgt_shift, db),
        )

    return _build_swap_out(req, db)


@router.get("/me", response_model=list[SwapRequestOut])
def my_swaps(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    my_shift_ids = [s.id for s in db.query(Shift.id).filter(Shift.user_id == current_user.id).all()]
    reqs = db.query(ShiftSwapRequest).filter(
        (ShiftSwapRequest.requester_id == current_user.id) |
        (ShiftSwapRequest.target_shift_id.in_(my_shift_ids))
    ).order_by(ShiftSwapRequest.created_at.desc()).all()
    return [_build_swap_out(r, db) for r in reqs]


@router.get("", response_model=list[SwapRequestOut])
def all_swaps(db: Session = Depends(get_db), _: User = Depends(require_manager)):
    reqs = db.query(ShiftSwapRequest).filter(
        ShiftSwapRequest.status == SwapStatus.accepted,
    ).order_by(ShiftSwapRequest.created_at.desc()).all()
    return [_build_swap_out(r, db) for r in reqs]


@router.put("/{swap_id}/accept", response_model=SwapRequestOut)
def accept_swap(swap_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    req = db.query(ShiftSwapRequest).filter(ShiftSwapRequest.id == swap_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Swap request not found")
    if req.target_shift.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your shift to accept")
    if req.status != SwapStatus.pending:
        raise HTTPException(status_code=400, detail="Request is no longer pending")
    req.status = SwapStatus.accepted
    db.commit()
    db.refresh(req)
    requester = db.query(User).filter(User.id == req.requester_id).first()
    if requester:
        send_swap_response_email(requester.email, requester.name, True, current_user.name)
    return _build_swap_out(req, db)


@router.put("/{swap_id}/reject", response_model=SwapRequestOut)
def reject_swap(swap_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    req = db.query(ShiftSwapRequest).filter(ShiftSwapRequest.id == swap_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Swap request not found")
    if req.target_shift.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your shift to reject")
    if req.status != SwapStatus.pending:
        raise HTTPException(status_code=400, detail="Request is no longer pending")
    req.status = SwapStatus.rejected
    db.commit()
    db.refresh(req)
    requester = db.query(User).filter(User.id == req.requester_id).first()
    if requester:
        send_swap_response_email(requester.email, requester.name, False, current_user.name)
    return _build_swap_out(req, db)


@router.put("/{swap_id}/approve", response_model=SwapRequestOut)
def approve_swap(swap_id: int, db: Session = Depends(get_db), _: User = Depends(require_manager)):
    req = db.query(ShiftSwapRequest).filter(ShiftSwapRequest.id == swap_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Swap request not found")
    if req.status != SwapStatus.accepted:
        raise HTTPException(status_code=400, detail="Swap must be accepted by both employees first")

    rs, ts = req.requester_shift, req.target_shift
    shift_info_a = _shift_label(rs, db)
    shift_info_b = _shift_label(ts, db)

    rs.user_id, ts.user_id = ts.user_id, rs.user_id
    req.status = SwapStatus.approved
    db.commit()
    db.refresh(req)

    requester = db.query(User).filter(User.id == req.requester_id).first()
    target_user = db.query(User).filter(User.id == rs.user_id).first()
    if requester:
        send_swap_decision_email(requester.email, requester.name, True, shift_info_a, shift_info_b)
    if target_user:
        send_swap_decision_email(target_user.email, target_user.name, True, shift_info_a, shift_info_b)

    return _build_swap_out(req, db)


@router.put("/{swap_id}/deny", response_model=SwapRequestOut)
def deny_swap(swap_id: int, db: Session = Depends(get_db), _: User = Depends(require_manager)):
    req = db.query(ShiftSwapRequest).filter(ShiftSwapRequest.id == swap_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Swap request not found")
    if req.status != SwapStatus.accepted:
        raise HTTPException(status_code=400, detail="Only accepted swaps can be denied")
    req.status = SwapStatus.denied
    db.commit()
    db.refresh(req)
    shift_info_a = _shift_label(req.requester_shift, db)
    shift_info_b = _shift_label(req.target_shift, db)
    requester = db.query(User).filter(User.id == req.requester_id).first()
    target_user = db.query(User).filter(User.id == req.target_shift.user_id).first()
    if requester:
        send_swap_decision_email(requester.email, requester.name, False, shift_info_a, shift_info_b)
    if target_user:
        send_swap_decision_email(target_user.email, target_user.name, False, shift_info_a, shift_info_b)
    return _build_swap_out(req, db)
