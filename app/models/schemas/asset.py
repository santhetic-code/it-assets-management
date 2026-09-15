from datetime import date
from typing import Optional
from pydantic import BaseModel


class AssetBase(BaseModel):
    kode_aset: Optional[str] = None
    nama: str
    kelompok: str
    sn_pid: Optional[str] = None
    tanggal_masuk: Optional[date] = None
    tanggal_keluar: Optional[date] = None
    kepemilikan: str
    lokasi: str
    status: str
    digunakan_oleh: Optional[str] = None


class AssetCreate(AssetBase):
    pass


class AssetUpdate(AssetBase):
    pass


class AssetResponse(AssetBase):
    id: int

    model_config = {"from_attributes": True}
