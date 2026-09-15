from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class UserBase(BaseModel):
    username: str
    full_name: str
    role: str
    is_active: Optional[bool] = True


class UserCreate(UserBase):
    password: str  # Menerima password mentah dari form UI


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None
    password: Optional[str] = None  # Jika password ingin diubah


class UserResponse(UserBase):
    id: int
    avatar: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}
