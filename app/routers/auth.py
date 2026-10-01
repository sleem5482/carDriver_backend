"""
Auth router — login endpoint.
Override: accepts phone + password (not email).
All timestamps are server-generated.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.models.user import User, UserStatus, UserRole
from app.schemas.auth import LoginRequest, AdminLoginRequest, TokenResponse
from app.services.auth_service import verify_password, create_access_token
from app.services.audit_service import log_action
from app.utils.exceptions import unauthorized

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    """
    Authenticate a user with phone number and password.

    - Looks up the user by mobile_number (phone).
    - Validates password against bcrypt hash.
    - Returns a JWT access token on success.
    - All login timestamps are server-generated (UTC).
    """
    user = db.query(User).filter(User.mobile_number == body.phone).first()

    if not user or not verify_password(body.password, user.hashed_password):
        raise unauthorized("Invalid phone number or password.")

    if user.status != UserStatus.ACTIVE:
        raise unauthorized("Account is inactive. Contact your administrator.")


    # Create JWT with server timestamp
    token = create_access_token(user_id=str(user.id), role=user.role.value)

    # Audit log
    log_action(
        db,
        user_id=str(user.id),
        action="LOGIN",
        new_value={"login_time": datetime.now(timezone.utc).isoformat(), "method": "phone"},
    )
    db.commit()

    return TokenResponse(access_token=token)


@router.post("/admin-login", response_model=TokenResponse)
def admin_login(body: AdminLoginRequest, db: Session = Depends(get_db)):
    """
    Dedicated admin login with static username and password.
    """
    if body.username != "admin" or body.password != "123456":
        raise unauthorized("Invalid admin credentials.")

    # Get the system admin user from the database to attach their ID to the token
    # (so foreign key constraints pass for audit logs and admin-created entities)
    admin_user = db.query(User).filter(User.role == UserRole.ADMIN).first()
    
    if not admin_user:
        raise unauthorized("System admin account not found in database.")

    # Create JWT with server timestamp
    token = create_access_token(user_id=str(admin_user.id), role=UserRole.ADMIN.value)

    # Audit log
    log_action(
        db,
        user_id=str(admin_user.id),
        action="LOGIN",
        new_value={"login_time": datetime.now(timezone.utc).isoformat(), "method": "admin_static"},
    )
    db.commit()

    return TokenResponse(access_token=token)
