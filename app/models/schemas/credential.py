from typing import Optional
from datetime import datetime
from pydantic import BaseModel

class CredentialBase(BaseModel):
    title: str
    url: Optional[str] = None
    username: str
    notes: Optional[str] = None

class CredentialCreate(CredentialBase):
    password: str # Wajib diisi saat membuat kredensial baru

class CredentialUpdate(BaseModel):
    """
    Semua field bersifat opsional. 
    Nanti di Service, kita akan menggunakan `exclude_unset=True` agar 
    hanya field yang benar-benar dikirim dari form yang di-update.
    """
    title: Optional[str] = None
    url: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    notes: Optional[str] = None

class CredentialResponse(CredentialBase):
    id: int
    created_at: datetime
    updated_at: datetime

    # Mengubah object SQLAlchemy menjadi dictionary JSON secara otomatis
    model_config = {"from_attributes": True}


# ========== VAULT CREDENTIAL SCHEMAS (Sistem Kredensial Dinamis) ==========
from typing import Dict, Any

class VaultBase(BaseModel):
    nama_sistem: str
    kategori: str
    kredensial_data: Dict[str, Any]  # Memastikan API bisa menerima format JSON apa pun
    akses_role: Optional[str] = "All"

class VaultCreate(VaultBase):
    pass

class VaultUpdate(VaultBase):
    pass

class VaultResponse(VaultBase):
    id: int

    model_config = {"from_attributes": True}
