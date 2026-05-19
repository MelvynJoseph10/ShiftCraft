import os
import smtplib
from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

from dotenv import load_dotenv
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY", "change-me-to-a-random-32-char-string")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "480"))
RESET_TOKEN_EXPIRE_MINUTES = 30

SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM = os.getenv("SMTP_FROM", SMTP_USER)
APP_URL = os.getenv("APP_URL", "http://127.0.0.1:8000")

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
bearer_scheme = HTTPBearer()


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode["exp"] = expire
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    token = credentials.credentials
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: Optional[int] = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = db.query(User).filter(User.id == int(user_id)).first()
    if user is None:
        raise credentials_exception
    return user


def require_manager(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "manager":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Manager access required")
    return current_user


def create_reset_token(user_id: int) -> str:
    return create_access_token(
        {"sub": str(user_id), "type": "reset"},
        expires_delta=timedelta(minutes=RESET_TOKEN_EXPIRE_MINUTES),
    )


def verify_reset_token(token: str) -> Optional[int]:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != "reset":
            return None
        user_id = payload.get("sub")
        return int(user_id) if user_id else None
    except JWTError:
        return None


def _send_email(to_email: str, subject: str, text: str, html: str) -> None:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = SMTP_FROM
    msg["To"] = to_email
    msg.attach(MIMEText(text, "plain"))
    msg.attach(MIMEText(html, "html"))
    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_FROM, to_email, msg.as_string())
    except Exception as exc:
        print(f"[EMAIL ERROR] {exc}")


def send_reset_email(to_email: str, reset_url: str) -> None:
    if not SMTP_HOST:
        print(f"[DEV] Password reset link for {to_email}:\n  {reset_url}")
        return
    text = f"Click the link to reset your ShiftCraft password:\n{reset_url}\n\nThis link expires in 30 minutes. If you didn't request this, you can ignore this email."
    html = f"""<div style="font-family:sans-serif;max-width:480px">
  <h2 style="color:#1a1a2e">ShiftCraft Password Reset</h2>
  <p>Click the button below to reset your password. The link expires in <strong>30 minutes</strong>.</p>
  <p><a href="{reset_url}" style="display:inline-block;background:#e94560;color:#fff;padding:0.6rem 1.25rem;border-radius:6px;text-decoration:none;font-weight:600">Reset Password</a></p>
  <p style="color:#718096;font-size:0.85rem">If you didn't request this, you can safely ignore this email.</p>
</div>"""
    _send_email(to_email, "ShiftCraft — Reset Your Password", text, html)


def send_shift_assigned_email(to_email: str, employee_name: str, facility_name: str, start_time: datetime, end_time: datetime) -> None:
    if not SMTP_HOST:
        print(f"[DEV] Shift assigned email for {to_email}: {facility_name} {start_time.strftime('%b %d %H:%M')}–{end_time.strftime('%H:%M')}")
        return
    start_str = start_time.strftime("%A, %b %d at %H:%M")
    end_str = end_time.strftime("%H:%M")
    text = f"Hi {employee_name},\n\nYou've been assigned a new shift at {facility_name}:\n{start_str} – {end_str}\n\nLog in to ShiftCraft to view your schedule."
    html = f"""<div style="font-family:sans-serif;max-width:480px">
  <h2 style="color:#1a1a2e">New Shift Assigned</h2>
  <p>Hi {employee_name},</p>
  <p>You've been assigned a shift at <strong>{facility_name}</strong>:</p>
  <p style="font-size:1.1rem;font-weight:600">{start_str} – {end_str}</p>
  <p><a href="{APP_URL}" style="display:inline-block;background:#e94560;color:#fff;padding:0.6rem 1.25rem;border-radius:6px;text-decoration:none;font-weight:600">View Schedule</a></p>
</div>"""
    _send_email(to_email, "ShiftCraft — New Shift Assigned", text, html)


def send_shift_cancelled_email(to_email: str, employee_name: str, facility_name: str, start_time: datetime, end_time: datetime) -> None:
    if not SMTP_HOST:
        print(f"[DEV] Shift cancelled email for {to_email}: {facility_name} {start_time.strftime('%b %d %H:%M')}–{end_time.strftime('%H:%M')}")
        return
    start_str = start_time.strftime("%A, %b %d at %H:%M")
    end_str = end_time.strftime("%H:%M")
    text = f"Hi {employee_name},\n\nYour shift at {facility_name} on {start_str} – {end_str} has been cancelled."
    html = f"""<div style="font-family:sans-serif;max-width:480px">
  <h2 style="color:#1a1a2e">Shift Cancelled</h2>
  <p>Hi {employee_name},</p>
  <p>Your shift at <strong>{facility_name}</strong> has been cancelled:</p>
  <p style="font-size:1.1rem;font-weight:600;color:#718096;text-decoration:line-through">{start_str} – {end_str}</p>
  <p><a href="{APP_URL}" style="display:inline-block;background:#e94560;color:#fff;padding:0.6rem 1.25rem;border-radius:6px;text-decoration:none;font-weight:600">View Schedule</a></p>
</div>"""
    _send_email(to_email, "ShiftCraft — Shift Cancelled", text, html)


def send_time_off_decision_email(to_email: str, employee_name: str, decision: str, start_date, end_date) -> None:
    if not SMTP_HOST:
        print(f"[DEV] Time-off {decision} email for {to_email}: {start_date} to {end_date}")
        return
    approved = decision == "approved"
    status_word = "Approved" if approved else "Denied"
    color = "#38a169" if approved else "#e53e3e"
    text = f"Hi {employee_name},\n\nYour time-off request from {start_date} to {end_date} has been {decision}."
    html = f"""<div style="font-family:sans-serif;max-width:480px">
  <h2 style="color:#1a1a2e">Time-Off Request {status_word}</h2>
  <p>Hi {employee_name},</p>
  <p>Your time-off request from <strong>{start_date}</strong> to <strong>{end_date}</strong> has been <span style="color:{color};font-weight:600">{decision}</span>.</p>
  <p><a href="{APP_URL}" style="display:inline-block;background:#e94560;color:#fff;padding:0.6rem 1.25rem;border-radius:6px;text-decoration:none;font-weight:600">View ShiftCraft</a></p>
</div>"""
    _send_email(to_email, f"ShiftCraft — Time-Off Request {status_word}", text, html)
