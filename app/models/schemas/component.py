from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class ComponentBase(BaseModel):
    asset_id: int
    name: str
    os_name: Optional[str] = None
    ram_spec: Optional[str] = None
    vga_spec: Optional[str] = None
    processor_spec: Optional[str] = None
    mainboard_spec: Optional[str] = None
    storage_spec: Optional[str] = None
    monitor: Optional[str] = None
    keyboard: Optional[str] = None
    mouse: Optional[str] = None
    psu: Optional[str] = None
    casing: Optional[str] = None


class ComponentCreate(ComponentBase):
    pass


class ComponentUpdate(BaseModel):
    asset_id: Optional[int] = None
    name: Optional[str] = None
    os_name: Optional[str] = None
    ram_spec: Optional[str] = None
    vga_spec: Optional[str] = None
    processor_spec: Optional[str] = None
    mainboard_spec: Optional[str] = None
    storage_spec: Optional[str] = None
    monitor: Optional[str] = None
    keyboard: Optional[str] = None
    mouse: Optional[str] = None
    psu: Optional[str] = None
    casing: Optional[str] = None


class ComponentResponse(ComponentBase):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
