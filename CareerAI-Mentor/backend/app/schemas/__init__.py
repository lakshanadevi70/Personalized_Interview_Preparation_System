from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, EmailStr, Field

class RegisterRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)
class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
class StudentProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    college: Optional[str]; degree: Optional[str]; branch: Optional[str]; current_year: Optional[int]; graduation_year: Optional[int]
    target_role: Optional[str]; experience_level: Optional[str]; technical_skills: list[str]; weekly_study_time: Optional[int]; learning_preference: Optional[str]
class CurrentUserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    name: str
    email: EmailStr
    created_at: datetime
    profile: Optional[StudentProfileResponse] = None

class OnboardingRequest(BaseModel):
    college: str | None = Field(default=None, max_length=200)
    degree: str | None = Field(default=None, max_length=120)
    branch: str | None = Field(default=None, max_length=120)
    current_year: int | None = Field(default=None, ge=1, le=8)
    graduation_year: int | None = Field(default=None, ge=2020, le=2100)
    target_role: str | None = Field(default=None, max_length=120)
    experience_level: str | None = Field(default=None, max_length=50)
    technical_skills: list[str] = Field(default_factory=list, max_length=50)
    weekly_study_time: int | None = Field(default=None, ge=1, le=80)
    learning_preference: str | None = Field(default=None, max_length=80)
