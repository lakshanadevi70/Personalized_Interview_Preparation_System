from datetime import UTC, datetime, timedelta
from uuid import UUID
import jwt
from fastapi import HTTPException, status
from pwdlib import PasswordHash
from app.config import get_settings

password_hash = PasswordHash.recommended()
def hash_password(password: str) -> str: return password_hash.hash(password)
def verify_password(password: str, hashed: str) -> bool: return password_hash.verify(password, hashed)
def create_access_token(user_id: UUID) -> str:
    settings = get_settings()
    return jwt.encode({"sub": str(user_id), "exp": datetime.now(UTC) + timedelta(minutes=settings.access_token_expire_minutes)}, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
def decode_access_token(token: str) -> UUID:
    settings = get_settings()
    try:
        return UUID(jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])["sub"])
    except (jwt.InvalidTokenError, KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not validate credentials", headers={"WWW-Authenticate": "Bearer"}) from exc
