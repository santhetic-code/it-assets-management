from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, Field

# ==========================================
# MASTER COMPONENT SCHEMAS
# ==========================================
class MasterComponentBase(BaseModel):
    category: str = Field(..., description="Kategori: CPU, RAM, OS, VGA, Storage, Monitor, Mainboard")
    name: str = Field(..., description="Nama spesifik komponen (unik)")
    description: Optional[str] = None

class MasterComponentCreate(MasterComponentBase):
    pass

class MasterComponentResponse(MasterComponentBase):
    id: int
    model_config = {"from_attributes": True}

# ==========================================
# COMPONENT SCHEMAS (Strict Foreign Key)
# ==========================================
class ComponentBase(BaseModel):
    name: str = Field(..., description="Identitas PC / Nama PC / User")
    pc_type: Optional[str] = Field(default="Operasional", description="Kategori PC")
    asset_id: Optional[int] = None
    
    # Wajib menggunakan ID dari master_components
    os_id: Optional[int] = None
    cpu_id: Optional[int] = None
    mainboard_id: Optional[int] = None
    ram_id: Optional[int] = None
    vga_id: Optional[int] = None
    storage_id: Optional[int] = None
    monitor_id: Optional[int] = None

    # Periferal string (belum di-master)
    keyboard: Optional[str] = None
    mouse: Optional[str] = None
    psu: Optional[str] = None
    casing: Optional[str] = None

class ComponentCreate(ComponentBase):
    pass

class ComponentUpdate(ComponentBase):
    update_reason: Optional[str] = Field(default=None, description="Wajib diisi jika mengupdate komponen untuk Audit Trail")

class ComponentResponse(ComponentBase):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    # Field tambahan untuk UI Frontend (mengambil dari @property di model)
    os: Optional[str] = "-"
    cpu: Optional[str] = "-"
    mainboard: Optional[str] = "-"
    ram: Optional[str] = "-"
    vga: Optional[str] = "-"
    storage: Optional[str] = "-"
    monitor_display: Optional[str] = "-"
    jenis_pc: Optional[str] = "-"
    last_update: Optional[str] = "-"

    model_config = {"from_attributes": True}

# ==========================================
# COMPONENT HISTORY SCHEMAS
# ==========================================
class ComponentHistoryResponse(BaseModel):
    id: int
    component_id: int
    user_id: Optional[int] = None
    action_type: str
    changes_detail: Any
    created_at: datetime

    model_config = {"from_attributes": True}
