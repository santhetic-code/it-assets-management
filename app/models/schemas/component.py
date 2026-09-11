from datetime import datetime
from enum import Enum
from typing import Optional, Union
from pydantic import BaseModel


class JenisPC(str, Enum):
    OPERASIONAL = "PC Operasional"
    SERVER = "PC Server"
    BACKUP = "PC Backup"
    OPERASIONAL_LEGACY = "Operasional"
    SERVER_LEGACY = "Server"
    BACKUP_LEGACY = "Backup"


class ComponentBase(BaseModel):
    asset_id: Optional[int] = None
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
    pc_type: Optional[Union[JenisPC, str]] = "Operasional"


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
    pc_type: Optional[Union[JenisPC, str]] = None


class ComponentResponse(ComponentBase):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
