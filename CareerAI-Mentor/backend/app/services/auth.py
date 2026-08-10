from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.security import create_access_token, hash_password, verify_password
from app.models import User
from app.schemas import LoginRequest, RegisterRequest

class AuthService:
    def register(self, db: Session, payload: RegisterRequest) -> str:
        email = str(payload.email).lower()
        if db.scalar(select(User).where(User.email == email)):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An account with this email already exists")
        user = User(name=payload.name.strip(), email=email, password_hash=hash_password(payload.password))
        db.add(user); db.commit(); db.refresh(user)
        return create_access_token(user.id)
    def login(self, db: Session, payload: LoginRequest) -> str:
        user = db.scalar(select(User).where(User.email == str(payload.email).lower()))
        if user is None or not verify_password(payload.password, user.password_hash):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
        return create_access_token(user.id)
