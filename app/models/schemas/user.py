from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class UserBase(BaseModel):
    username: str
    full_name: Optional[str] = None
    role: str
    is_active: Optional[bool] = True
    # Tambahan Kolom Profil
    email: Optional[str] = None
    phone: Optional[str] = None
    department: Optional[str] = None


class UserCreate(UserBase):
    # Validasi Password Backend (Min 8 Karakter)
    password: str = Field(..., min_length=8)


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    department: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None
    password: Optional[str] = None


class ChangePasswordRequest(BaseModel):
    username: str
    old_password: str
    new_password: str = Field(..., min_length=8)


class UserResponse(UserBase):
    id: int
    avatar: Optional[str] = None
    is_online: Optional[bool] = False
    last_login: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}
