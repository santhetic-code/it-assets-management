from pydantic import BaseModel
from typing import Optional, Dict, Any

class VaultBase(BaseModel):
    name: str
    category: str
    url: Optional[str] = None
    description: Optional[str] = None

# Skema saat Super Admin menyimpan data baru
class VaultCreate(VaultBase):
    secrets: Dict[str, Any]  # Menerima objek JSON dinamis tanpa batas

# Skema yang dikembalikan ke UI (tidak mengandung rahasia)
class VaultResponse(VaultBase):
    id: int

    class Config:
        from_attributes = True

# Skema saat tombol "Reveal" ditekan
class DecryptResponse(BaseModel):
    secrets: Dict[str, Any]  # Mengembalikan JSON utuh yang sudah didekripsi

# Skema untuk toggle akses staf
class VaultAccessToggle(BaseModel):
    user_id: int
    has_access: bool
