"""
Auth service — password hashing, JWT creation & verification.
"""

from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt


from app.config import get_settings

settings = get_settings()

import bcrypt

def hash_password(plain: str) -> str:
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(plain.encode('utf-8'), salt)
    return hashed.decode('utf-8')

def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode('utf-8'), hashed.encode('utf-8'))
    except ValueError:
        return False


# ── JWT ───────────────────────────────────────────────────

def create_access_token(user_id: str, role: str) -> str:
    """
    Create a JWT access token.
    All timestamps are server-generated (UTC).
    """
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": user_id,
        "role": role,
        "iat": now,
        "exp": expire,
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict:
    """
    Decode & validate a JWT token.
    Raises JWTError on invalid/expired tokens.
    """
    try:
        payload = jwt.decode(
            token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
        )
        return payload
    except JWTError:
        raise
