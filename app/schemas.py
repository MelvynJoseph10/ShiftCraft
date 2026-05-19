from datetime import date, datetime, time
from typing import Optional

from pydantic import BaseModel, EmailStr

from app.models import EmployeeRole, ShiftStatus, TimeOffStatus, UserRole


class UserCreate(BaseModel):
    name: str
    email: EmailStr
    password: str
    role: UserRole
    employee_role: Optional[EmployeeRole] = None


class UserOut(BaseModel):
    id: int
    name: str
    email: str
    role: UserRole
    employee_role: Optional[EmployeeRole] = None
    is_active: bool
    hired_at: datetime

    model_config = {"from_attributes": True}


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class ResetPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordConfirmRequest(BaseModel):
    token: str
    new_password: str


class UserUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    employee_role: Optional[EmployeeRole] = None


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class FacilityCreate(BaseModel):
    name: str
    opening_time: time
    closing_time: time


class FacilityUpdate(BaseModel):
    name: Optional[str] = None
    opening_time: Optional[time] = None
    closing_time: Optional[time] = None


class FacilityOut(BaseModel):
    id: int
    name: str
    opening_time: time
    closing_time: time

    model_config = {"from_attributes": True}


class AvailabilityCreate(BaseModel):
    day_of_week: int
    start_time: time
    end_time: time


class AvailabilityOut(BaseModel):
    id: int
    user_id: int
    day_of_week: int
    start_time: time
    end_time: time

    model_config = {"from_attributes": True}


class ShiftCreate(BaseModel):
    facility_id: int
    user_id: int
    start_time: datetime
    end_time: datetime


class ShiftOut(BaseModel):
    id: int
    facility_id: int
    user_id: int
    start_time: datetime
    end_time: datetime
    status: ShiftStatus

    model_config = {"from_attributes": True}


class TimeOffCreate(BaseModel):
    start_date: date
    end_date: date
    reason: str


class DashboardStats(BaseModel):
    upcoming_shifts: int
    this_week_shifts: int
    this_week_hours: float
    pending_time_off: int
    active_employees: Optional[int] = None


class EmployeeHoursOut(BaseModel):
    employee_id: int
    employee_name: str
    scheduled_hours: float
    completed_hours: float
    total_shifts: int


class TimeOffOut(BaseModel):
    id: int
    user_id: int
    start_date: date
    end_date: date
    reason: str
    status: TimeOffStatus
    reviewed_by: Optional[int] = None
    created_at: datetime

    model_config = {"from_attributes": True}
