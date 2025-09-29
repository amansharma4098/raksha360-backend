# app/auth.py
import os
from passlib.context import CryptContext
from datetime import datetime, timedelta
from jose import jwt

# Global app secret (SAME for all hospitals/users). Change in production!
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = int(os.getenv("ACCESS_TOKEN_EXPIRE_HOURS", 12))

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """
    Hash a plaintext password using bcrypt.
    """
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a plaintext password against a stored hash.
    """
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(data: dict, hospital_token_version: int = 0, expires_delta: timedelta = None) -> str:
    """
    Create a JWT access token from 'data' (dict of claims).
    Adds 'exp' (expiry) and 'tv' (token_version) fields.
    """
    to_encode = data.copy()
    if expires_delta is None:
        expires_delta = timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    expire = datetime.utcnow() + expires_delta
    to_encode.update({
        "exp": expire,
        "tv": hospital_token_version
    })
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def decode_and_verify_token(token: str, expected_token_version: int = None) -> dict:
    """
    Decode JWT token, verify signature and optional token_version.
    Raises ValueError if invalid or revoked.
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if expected_token_version is not None:
            tv = payload.get("tv", 0)
            if tv != expected_token_version:
                raise ValueError("Token version mismatch (token revoked)")
        return payload
    except Exception as e:
        raise ValueError(f"Invalid token: {e}")
