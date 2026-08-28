from typing import Optional
from pydantic import BaseModel


class ComponentBase(BaseModel):
    asset_id: Optional[int] = None
    name: Optional[str] = None
    assigned_to: Optional[str] = None
    pc_category: Optional[str] = None
    os_name: Optional[str] = None
    processor_spec: Optional[str] = None
    mainboard_spec: Optional[str] = None
    ram_spec: Optional[str] = None
    vga_spec: Optional[str] = None
    storage_spec: Optional[str] = None
    location: Optional[str] = None
    spesifikasi: Optional[str] = None


class ComponentCreate(ComponentBase):
    pass


class ComponentUpdate(BaseModel):
    asset_id: Optional[int] = None
    name: Optional[str] = None
    assigned_to: Optional[str] = None
    pc_category: Optional[str] = None
    os_name: Optional[str] = None
    processor_spec: Optional[str] = None
    mainboard_spec: Optional[str] = None
    ram_spec: Optional[str] = None
    vga_spec: Optional[str] = None
    storage_spec: Optional[str] = None
    location: Optional[str] = None
    spesifikasi: Optional[str] = None


class ComponentResponse(ComponentBase):
    id: int

    model_config = {"from_attributes": True}
