from datetime import datetime
from enum import Enum
from typing import Optional, Union
from pydantic import BaseModel, Field


class JenisPC(str, Enum):
    OPERASIONAL = "PC Operasional"
    SERVER = "PC Server"
    BACKUP = "PC Backup"
    OPERASIONAL_LEGACY = "Operasional"
    SERVER_LEGACY = "Server"
    BACKUP_LEGACY = "Backup"


# ==========================================
# MASTER COMPONENT SCHEMAS
# ==========================================
class MasterComponentBase(BaseModel):
    category: str = Field(..., description="Kategori: CPU, RAM, OS, VGA, Storage, Monitor")
    name: str = Field(..., description="Nama spesifik komponen (unik)")
    description: Optional[str] = None


class MasterComponentCreate(MasterComponentBase):
    pass


class MasterComponentResponse(MasterComponentBase):
    id: int

    model_config = {"from_attributes": True}


# ==========================================
# COMPONENT SCHEMAS (Free-text — lama, dipertahankan)
# ==========================================
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


# ==========================================
# COMPONENT SCHEMAS v2 (Master FK — baru)
# ==========================================
class ComponentCreateV2(BaseModel):
    """Skema baru menggunakan ID referensi ke master_components."""
    asset_id: int = Field(..., description="ID dari aset fisik di tabel assets")
    jenis_pc: str = Field(default="PC Operasional")
    os_id: Optional[int] = None
    cpu_id: Optional[int] = None
    mainboard_id: Optional[int] = None
    ram_id: Optional[int] = None
    vga_id: Optional[int] = None
    storage_id: Optional[int] = None
    monitor_id: Optional[int] = None
    keyboard: Optional[str] = None
    mouse: Optional[str] = None


class ComponentUpdateV2(ComponentCreateV2):
    """Skema update dengan catatan alasan (untuk Audit Trail)."""
    update_reason: str = Field(..., description="Alasan perubahan: Upgrade RAM, Ganti HDD, dll.")


class ComponentResponseV2(ComponentCreateV2):
    id: int
    # Nama resolusi dari relasi — diisi oleh endpoint, bukan ORM langsung
    os_name_resolved: Optional[str] = None
    cpu_name_resolved: Optional[str] = None
    mainboard_name_resolved: Optional[str] = None
    ram_name_resolved: Optional[str] = None
    vga_name_resolved: Optional[str] = None
    storage_name_resolved: Optional[str] = None
    monitor_name_resolved: Optional[str] = None

    model_config = {"from_attributes": True}


# ==========================================
# COMPONENT HISTORY SCHEMAS
# ==========================================
class ComponentHistoryResponse(BaseModel):
    id: int
    component_id: int
    user_id: Optional[int] = None
    action_type: str
    changes_detail: str
    created_at: datetime

    model_config = {"from_attributes": True}
