from typing import Optional
from pydantic import BaseModel

class ComponentBase(BaseModel):
    asset_id: int
    name: str
    spesifikasi: Optional[str] = None

class ComponentCreate(ComponentBase):
    pass

class ComponentUpdate(BaseModel):
    name: Optional[str] = None
    spesifikasi: Optional[str] = None

class ComponentResponse(ComponentBase):
    id: int

    model_config = {"from_attributes": True}
