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
# COMPONENT SCHEMAS (Free-text — diperbarui dengan periferal & kompatibilitas)
# ==========================================
class ComponentBase(BaseModel):
    identitas_pc: Optional[str] = None
    jenis_pc: Optional[str] = "PC Operasional"
    cpu: Optional[str] = None
    mainboard: Optional[str] = None
    ram: Optional[str] = None
    storage: Optional[str] = None
    vga: Optional[str] = None
    os: Optional[str] = None

    # Tambahan 3 Field Periferal (Wajib Sinkron dengan Modal)
    monitor: Optional[str] = None
    keyboard: Optional[str] = None
    mouse: Optional[str] = None

    # Kompatibilitas model lama & ORM
    name: Optional[str] = None
    asset_id: Optional[int] = None
    os_name: Optional[str] = None
    ram_spec: Optional[str] = None
    vga_spec: Optional[str] = None
    processor_spec: Optional[str] = None
    mainboard_spec: Optional[str] = None
    storage_spec: Optional[str] = None
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
# COMPONENT SCHEMAS v2 (Input Manual Bebas String)
# ==========================================
from pydantic import model_validator
from typing import Any


class ComponentCreateV2(BaseModel):
    """Skema input manual spesifikasi PC (bebas teks tanpa kunci Master FK)."""
    identitas_pc: Optional[str] = Field(default=None, description="Identitas PC / Nama PC / User")
    name: Optional[str] = Field(default=None, description="Alias untuk identitas_pc")
    jenis_pc: Optional[str] = Field(default="PC Operasional", description="Kategori PC (Operasional, Server, Backup)")
    pc_type: Optional[str] = Field(default=None, description="Alias untuk jenis_pc")
    
    cpu: Optional[str] = Field(default=None, description="Processor (CPU)")
    processor_spec: Optional[str] = Field(default=None, description="Alias untuk cpu")
    mainboard: Optional[str] = Field(default=None, description="Mainboard / Motherboard")
    mainboard_spec: Optional[str] = Field(default=None, description="Alias untuk mainboard")
    ram: Optional[str] = Field(default=None, description="Kapasitas RAM")
    ram_spec: Optional[str] = Field(default=None, description="Alias untuk ram")
    storage: Optional[str] = Field(default=None, description="Penyimpanan (SSD/HDD)")
    storage_spec: Optional[str] = Field(default=None, description="Alias untuk storage")
    vga: Optional[str] = Field(default=None, description="Kartu Grafis (VGA/GPU)")
    vga_spec: Optional[str] = Field(default=None, description="Alias untuk vga")
    os: Optional[str] = Field(default=None, description="Sistem Operasi (OS)")
    os_name: Optional[str] = Field(default=None, description="Alias untuk os")
    
    monitor: Optional[str] = None
    keyboard: Optional[str] = None
    mouse: Optional[str] = None
    asset_id: Optional[int] = Field(default=None, description="ID aset fisik (kini opsional)")

    # Kompatibilitas mundur jika ada pemanggil lama
    os_id: Optional[int] = None
    cpu_id: Optional[int] = None
    mainboard_id: Optional[int] = None
    ram_id: Optional[int] = None
    vga_id: Optional[int] = None
    storage_id: Optional[int] = None
    monitor_id: Optional[int] = None

    @model_validator(mode="before")
    @classmethod
    def normalize_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            # Normalisasi Identitas PC
            pc_name = data.get("identitas_pc") or data.get("name")
            if pc_name:
                data["identitas_pc"] = pc_name
                data["name"] = pc_name
            # Normalisasi Kategori PC
            cat = data.get("jenis_pc") or data.get("pc_type")
            if cat:
                data["jenis_pc"] = cat
                data["pc_type"] = cat
            # Normalisasi Komponen Hardware
            if "cpu" in data and not data.get("processor_spec"):
                data["processor_spec"] = data["cpu"]
            elif "processor_spec" in data and not data.get("cpu"):
                data["cpu"] = data["processor_spec"]

            if "mainboard" in data and not data.get("mainboard_spec"):
                data["mainboard_spec"] = data["mainboard"]
            elif "mainboard_spec" in data and not data.get("mainboard"):
                data["mainboard"] = data["mainboard_spec"]

            if "ram" in data and not data.get("ram_spec"):
                data["ram_spec"] = data["ram"]
            elif "ram_spec" in data and not data.get("ram"):
                data["ram"] = data["ram_spec"]

            if "storage" in data and not data.get("storage_spec"):
                data["storage_spec"] = data["storage"]
            elif "storage_spec" in data and not data.get("storage"):
                data["storage"] = data["storage_spec"]

            if "vga" in data and not data.get("vga_spec"):
                data["vga_spec"] = data["vga"]
            elif "vga_spec" in data and not data.get("vga"):
                data["vga"] = data["vga_spec"]

            if "os" in data and not data.get("os_name"):
                data["os_name"] = data["os"]
            elif "os_name" in data and not data.get("os"):
                data["os"] = data["os_name"]
        return data


class ComponentUpdateV2(ComponentCreateV2):
    """Skema update dengan alasan perubahan opsional/wajib untuk Audit Trail."""
    update_reason: Optional[str] = Field(default=None, description="Alasan perubahan spesifikasi")


class ComponentResponseV2(ComponentCreateV2):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

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
