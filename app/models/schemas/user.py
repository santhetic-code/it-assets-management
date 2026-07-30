from typing import Optional
from datetime import datetime
from pydantic import BaseModel

class UserBase(BaseModel):
    username: str
    role: str = "Auditor"
    avatar: Optional[str] = None

class UserCreate(UserBase):
    password: str

class UserUpdate(BaseModel):
    username: Optional[str] = None
    password: Optional[str] = None
    role: Optional[str] = None
    avatar: Optional[str] = None

class UserResponse(UserBase):
    id: int
    created_at: datetime

    model_config = {"from_attributes": True}
