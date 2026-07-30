from typing import Optional
from datetime import date
from pydantic import BaseModel

class MaintenanceBase(BaseModel):
    asset_id: int
    status: str = "Aman"
    next_schedule_date: Optional[date] = None
    notes: Optional[str] = None

class MaintenanceCreate(MaintenanceBase):
    pass

class MaintenanceUpdate(BaseModel):
    status: Optional[str] = None
    next_schedule_date: Optional[date] = None
    notes: Optional[str] = None

class MaintenanceResponse(MaintenanceBase):
    id: int

    model_config = {"from_attributes": True}
