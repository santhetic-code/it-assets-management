from typing import Literal, Optional
from pydantic import BaseModel


class NetworkIPBase(BaseModel):
    ip_address: str
    ip_type: Optional[str] = "Operasional"
    assigned_to: Optional[str] = None
    mac_address: Optional[str] = None
    description: Optional[str] = None
    status: Literal["Aktif", "Offline"] = "Aktif"


class NetworkIPCreate(NetworkIPBase):
    pass


class NetworkIPUpdate(BaseModel):
    ip_address: Optional[str] = None
    ip_type: Optional[str] = None
    assigned_to: Optional[str] = None
    mac_address: Optional[str] = None
    description: Optional[str] = None
    status: Optional[Literal["Aktif", "Offline"]] = None


class NetworkIPResponse(NetworkIPBase):
    id: int

    model_config = {"from_attributes": True}
