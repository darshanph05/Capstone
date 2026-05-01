from pydantic import BaseModel, EmailStr, Field
from uuid import UUID
from datetime import datetime
from typing import Optional
from enum import Enum

class RoleCodeEnum(str, Enum):
    RESEARCHER = "RESEARCHER"
    ADMIN = "ADMIN"

# Token Schemas
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: Optional[str] = None


class LoginRequest(BaseModel):
    username: EmailStr
    password: str = Field(..., max_length=72, description="Password must be at most 72 characters long")

# User Schemas
class UserBase(BaseModel):
    email: EmailStr

class UserCreate(UserBase):
    password: str = Field(..., max_length=72, description="Password must be at most 72 characters long")
    role_code: RoleCodeEnum

class RoleResponse(BaseModel):
    id: int
    name: str
    code: str

    class Config:
        from_attributes = True

class UserResponse(UserBase):
    id: UUID
    created_at: datetime
    role: RoleResponse

    class Config:
        from_attributes = True
