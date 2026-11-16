from collections.abc import Generator
from datetime import datetime, timezone
from urllib.parse import urlsplit

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.security import hash_secret
from app.models import AuthSession, Role, User


def get_db() -> Generator[Session, None, None]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    raw_secret = request.cookies.get("durga_session")
    if not raw_secret:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Please sign in")

    auth_session = db.scalar(
        select(AuthSession).where(
            AuthSession.secret_hash == hash_secret(raw_secret),
            AuthSession.revoked_at.is_(None),
        )
    )
    if auth_session is None or auth_session.expires_at <= datetime.now(timezone.utc):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Your session has expired")

    user = db.scalar(
        select(User)
        .options(selectinload(User.roles).selectinload(Role.permissions))
        .where(User.id == auth_session.user_id, User.active.is_(True))
    )
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Please sign in")
    return user


def require_permission(code: str):
    def dependency(user: User = Depends(get_current_user)) -> User:
        granted = {permission.code for role in user.roles for permission in role.permissions}
        if code not in granted:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have access to this action")
        return user

    return dependency


def require_customer(user: User = Depends(get_current_user)) -> User:
    if user.account_type != "customer" or user.customer is None or user.phone_verified_at is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="A verified customer account is required")
    return user


def require_same_origin(request: Request) -> None:
    origin = request.headers.get("origin")
    if not origin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Request origin is required")
    expected = urlsplit(get_settings().app_origin)
    received = urlsplit(origin)
    if (expected.scheme, expected.netloc) != (received.scheme, received.netloc):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Request origin is not allowed")
