from pydantic import BaseModel
from typing import Optional
from datetime import datetime

# Skema Dasar
class VaultBase(BaseModel):
    name: str
    category: str
    url: Optional[str] = None
    username: Optional[str] = None
    description: Optional[str] = None

# Skema Saat Super Admin Menyimpan Data Baru
class VaultCreate(VaultBase):
    password: str  # Teks murni, akan dienkripsi di backend

# Skema Saat Tabel Dimuat (Sandi Dihilangkan Sepenuhnya!)
class VaultResponse(VaultBase):
    id: int
    created_at: datetime

    model_config = {"from_attributes": True}

# Skema Khusus Saat Tombol "👁️ Reveal" Diklik
class DecryptResponse(BaseModel):
    password: str
