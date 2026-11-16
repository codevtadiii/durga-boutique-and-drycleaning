import re
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_user, get_db, require_same_origin
from app.api.schemas import LoginInput, RegistrationRequestInput
from app.core.config import get_settings
from app.core.security import hash_secret, new_session_secret, verify_pin
from app.models import AuthSession, LoginAttempt, RegistrationRequest, Role, User

router = APIRouter(prefix="/api/v1/auth", tags=["authentication"])


def normalize_phone(value: str) -> str:
    digits = re.sub(r"\D", "", value)
    if len(digits) == 10:
        digits = "91" + digits
    elif len(digits) == 11 and digits.startswith("0"):
        digits = "91" + digits[1:]
    if not 12 <= len(digits) <= 15:
        raise HTTPException(status_code=422, detail="Enter a valid mobile number")
    return f"+{digits}"


def _enforce_login_limit(db: Session, phone_hash: str, client_hash: str, now: datetime) -> None:
    cutoff = now - timedelta(minutes=15)
    client_failures = db.scalar(
        select(func.count(LoginAttempt.id)).where(
            LoginAttempt.client_hash == client_hash,
            LoginAttempt.succeeded.is_(False),
            LoginAttempt.occurred_at >= cutoff,
        )
    ) or 0
    phone_failures = db.scalar(
        select(func.count(LoginAttempt.id)).where(
            LoginAttempt.phone_hash == phone_hash,
            LoginAttempt.succeeded.is_(False),
            LoginAttempt.occurred_at >= cutoff,
        )
    ) or 0
    if client_failures >= 10 or phone_failures >= 10:
        raise HTTPException(status_code=429, detail="Too many attempts. Please wait and try again.")


def _login(
    request: Request,
    response: Response,
    payload: LoginInput,
    account_type: str,
    db: Session,
) -> dict:
    now = datetime.now(timezone.utc)
    phone = normalize_phone(payload.phone)
    phone_hash = hash_secret(phone)
    client_hash = hash_secret(request.client.host if request.client else "unknown")
    _enforce_login_limit(db, phone_hash, client_hash, now)

    user = db.scalar(
        select(User)
        .options(selectinload(User.roles).selectinload(Role.permissions))
        .where(User.phone == phone, User.account_type == account_type, User.active.is_(True))
    )
    pin_valid = verify_pin(payload.pin, user.pin_hash if user else None)
    verified = user is not None and (account_type != "customer" or user.phone_verified_at is not None)
    valid = bool(user and user.active and verified and pin_valid)

    db.add(LoginAttempt(phone_hash=phone_hash, client_hash=client_hash, occurred_at=now, succeeded=valid))
    db.commit()
    if not valid or user is None:
        raise HTTPException(status_code=401, detail="The mobile number or PIN is incorrect")

    session_secret = new_session_secret()
    settings = get_settings()
    db.add(
        AuthSession(
            user_id=user.id,
            secret_hash=hash_secret(session_secret),
            expires_at=now + timedelta(days=settings.session_ttl_days),
        )
    )
    db.commit()
    response.set_cookie(
        "durga_session",
        session_secret,
        max_age=settings.session_ttl_days * 24 * 60 * 60,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
        path="/",
    )
    return {
        "id": str(user.id),
        "account_type": user.account_type,
        "customer_id": str(user.customer.id) if user.customer else None,
        "permissions": sorted({permission.code for role in user.roles for permission in role.permissions}),
    }


@router.post("/customer/register", status_code=status.HTTP_202_ACCEPTED, dependencies=[Depends(require_same_origin)])
def request_customer_registration(payload: RegistrationRequestInput, db: Session = Depends(get_db)) -> dict[str, str]:
    request = RegistrationRequest(
        full_name=payload.full_name.strip(),
        phone=normalize_phone(payload.phone),
        preferred_language=payload.preferred_language,
        whatsapp_order_updates=payload.whatsapp_order_updates,
        whatsapp_marketing=payload.whatsapp_marketing,
        consent_recorded_at=datetime.now(timezone.utc)
        if payload.whatsapp_order_updates or payload.whatsapp_marketing
        else None,
    )
    db.add(request)
    db.commit()
    return {"request_id": str(request.id), "message": "Your request is saved. Shop staff will help verify your account."}


@router.post("/customer/pin/login", dependencies=[Depends(require_same_origin)])
def customer_login(
    payload: LoginInput,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> dict:
    return _login(request, response, payload, "customer", db)


@router.post("/staff/pin/login", dependencies=[Depends(require_same_origin)])
def staff_login(
    payload: LoginInput,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> dict:
    return _login(request, response, payload, "staff", db)


@router.get("/session")
def current_session(user: User = Depends(get_current_user)) -> dict:
    return {
        "id": str(user.id),
        "account_type": user.account_type,
        "customer_id": str(user.customer.id) if user.customer else None,
        "permissions": sorted({permission.code for role in user.roles for permission in role.permissions}),
    }


@router.post("/logout", dependencies=[Depends(require_same_origin)])
def logout(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> dict[str, str]:
    raw_secret = request.cookies.get("durga_session")
    if raw_secret:
        session = db.scalar(select(AuthSession).where(AuthSession.secret_hash == hash_secret(raw_secret)))
        if session and session.revoked_at is None:
            session.revoked_at = datetime.now(timezone.utc)
            db.commit()
    response.delete_cookie("durga_session", path="/", httponly=True, samesite="lax")
    return {"message": "You are signed out"}
