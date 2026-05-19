import enum
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Time,
)
from sqlalchemy.orm import relationship

from app.database import Base


class UserRole(str, enum.Enum):
    manager = "manager"
    employee = "employee"


class EmployeeRole(str, enum.Enum):
    junior = "junior"
    experienced = "experienced"
    senior = "senior"


class ShiftStatus(str, enum.Enum):
    scheduled = "scheduled"
    completed = "completed"
    cancelled = "cancelled"


class TimeOffStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    denied = "denied"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(Enum(UserRole), nullable=False)
    employee_role = Column(Enum(EmployeeRole), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    hired_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    availability = relationship("Availability", back_populates="user", foreign_keys="Availability.user_id")
    shifts = relationship("Shift", back_populates="user", foreign_keys="Shift.user_id")
    time_off_requests = relationship("TimeOffRequest", back_populates="user", foreign_keys="TimeOffRequest.user_id")


class Facility(Base):
    __tablename__ = "facilities"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    opening_time = Column(Time, nullable=False)
    closing_time = Column(Time, nullable=False)

    shifts = relationship("Shift", back_populates="facility")


class Availability(Base):
    __tablename__ = "availability"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    day_of_week = Column(Integer, nullable=False)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)

    user = relationship("User", back_populates="availability", foreign_keys=[user_id])


class Shift(Base):
    __tablename__ = "shifts"

    id = Column(Integer, primary_key=True, index=True)
    facility_id = Column(Integer, ForeignKey("facilities.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)
    status = Column(Enum(ShiftStatus), default=ShiftStatus.scheduled, nullable=False)

    facility = relationship("Facility", back_populates="shifts")
    user = relationship("User", back_populates="shifts", foreign_keys=[user_id])


class TimeOffRequest(Base):
    __tablename__ = "time_off_requests"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    reason = Column(String, nullable=False)
    status = Column(Enum(TimeOffStatus), default=TimeOffStatus.pending, nullable=False)
    reviewed_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    user = relationship("User", back_populates="time_off_requests", foreign_keys=[user_id])
    reviewer = relationship("User", foreign_keys=[reviewed_by])
