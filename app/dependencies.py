"""
Shared FastAPI dependencies — DB session, current user extraction.
"""

import uuid
from typing import Annotated

from fastapi import Depends, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.user import User, UserRole
from app.services.auth_service import decode_access_token
from app.utils.exceptions import unauthorized, forbidden

# ── DB Session ────────────────────────────────────────────

def get_db():
    """Yield a database session per request, auto-close on completion."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ── Auth Dependencies ────────────────────────────────────

security = HTTPBearer()


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
    db: Session = Depends(get_db),
) -> User:
    """
    Extract and validate the JWT bearer token.
    Returns the authenticated User ORM instance.
    """
    token = credentials.credentials
    try:
        payload = decode_access_token(token)
    except JWTError:
        raise unauthorized("Token is invalid or expired.")

    user_id = payload.get("sub")
    if user_id is None:
        raise unauthorized("Token payload missing subject.")

    user = db.query(User).filter(User.id == uuid.UUID(user_id)).first()
    if user is None:
        raise unauthorized("User not found.")

    return user


def require_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    """Ensure the current user has ADMIN role."""
    if current_user.role != UserRole.ADMIN:
        raise forbidden("Admin access required.")
    return current_user


def require_driver(
    current_user: User = Depends(get_current_user),
) -> User:
    """Ensure the current user has DRIVER role."""
    if current_user.role != UserRole.DRIVER:
        raise forbidden("Driver access required.")
    return current_user
