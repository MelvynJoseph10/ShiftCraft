from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth import get_current_user, hash_password, require_manager
from app.database import get_db
from app.models import User, UserRole
from app.schemas import UserCreate, UserOut, UserUpdate

router = APIRouter(prefix="/employees", tags=["employees"])


@router.get("/managers", response_model=list[UserOut])
def list_managers(db: Session = Depends(get_db), _: User = Depends(require_manager)):
    return db.query(User).filter(User.role == UserRole.manager, User.is_active == True).all()  # noqa: E712


@router.get("/inactive", response_model=list[UserOut])
def list_inactive(db: Session = Depends(get_db), _: User = Depends(require_manager)):
    return db.query(User).filter(User.is_active == False).all()  # noqa: E712


@router.get("", response_model=list[UserOut])
def list_employees(db: Session = Depends(get_db), _: User = Depends(require_manager)):
    return db.query(User).filter(User.role == UserRole.employee, User.is_active == True).all()  # noqa: E712


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_employee(payload: UserCreate, db: Session = Depends(get_db), _: User = Depends(require_manager)):
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    user = User(
        name=payload.name,
        email=payload.email,
        password_hash=hash_password(payload.password),
        role=payload.role,
        employee_role=payload.employee_role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.get("/{employee_id}", response_model=UserOut)
def get_employee(employee_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    user = db.query(User).filter(User.id == employee_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Employee not found")
    return user


@router.put("/{employee_id}", response_model=UserOut)
def update_employee(employee_id: int, payload: UserUpdate, db: Session = Depends(get_db), _: User = Depends(require_manager)):
    user = db.query(User).filter(User.id == employee_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Employee not found")
    if payload.name is not None:
        user.name = payload.name
    if payload.email is not None:
        conflict = db.query(User).filter(User.email == payload.email, User.id != employee_id).first()
        if conflict:
            raise HTTPException(status_code=400, detail="Email already in use")
        user.email = payload.email
    if payload.employee_role is not None:
        user.employee_role = payload.employee_role
    db.commit()
    db.refresh(user)
    return user


@router.put("/{employee_id}/reactivate", response_model=UserOut)
def reactivate_employee(employee_id: int, db: Session = Depends(get_db), _: User = Depends(require_manager)):
    user = db.query(User).filter(User.id == employee_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Employee not found")
    user.is_active = True
    db.commit()
    db.refresh(user)
    return user


@router.delete("/{employee_id}", response_model=UserOut)
def delete_employee(employee_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_manager)):
    if employee_id == current_user.id:
        raise HTTPException(status_code=400, detail="You cannot deactivate your own account")
    user = db.query(User).filter(User.id == employee_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Employee not found")
    user.is_active = False
    db.commit()
    db.refresh(user)
    return user
