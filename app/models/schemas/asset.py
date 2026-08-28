from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class AssetBase(BaseModel):
    asset_tag: str
    name: str
    category: str
    status: str = "Digunakan"
    assigned_to: Optional[str] = None
    location: Optional[str] = None
    serial_number: Optional[str] = None
    condition: Optional[str] = "Baru"
    usage_status: Optional[str] = None


class AssetCreate(AssetBase):
    pass


class AssetUpdate(BaseModel):
    asset_tag: Optional[str] = None
    name: Optional[str] = None
    category: Optional[str] = None
    status: Optional[str] = None
    assigned_to: Optional[str] = None
    location: Optional[str] = None
    serial_number: Optional[str] = None
    condition: Optional[str] = None
    usage_status: Optional[str] = None


class AssetResponse(AssetBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
