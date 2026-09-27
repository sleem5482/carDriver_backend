"""
Auth schemas — login request (phone + password) and token response.
"""

from pydantic import BaseModel


class LoginRequest(BaseModel):
    """
    Login with phone number and password.
    Override: accepts phone (not email) as the primary credential.
    """
    phone: str
    password: str


class AdminLoginRequest(BaseModel):
    """
    Dedicated admin login with static username and password.
    """
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenPayload(BaseModel):
    sub: str        # user ID as string
    role: str       # ADMIN | DRIVER
    exp: int | None = None
