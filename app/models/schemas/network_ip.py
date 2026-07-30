from typing import Optional
from pydantic import BaseModel

class NetworkIPBase(BaseModel):
    ip_address: str
    mac_address: Optional[str] = None
    description: Optional[str] = None
    status: str = "Aktif"

class NetworkIPCreate(NetworkIPBase):
    pass

class NetworkIPUpdate(BaseModel):
    ip_address: Optional[str] = None
    mac_address: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None

class NetworkIPResponse(NetworkIPBase):
    id: int

    model_config = {"from_attributes": True}
