from datetime import date
from typing import Optional
from pydantic import BaseModel


class MaintenanceBase(BaseModel):
    asset_id: int
    task_type: Optional[str] = None
    location_target: Optional[str] = None
    last_maintenance_date: Optional[date] = None
    next_schedule_date: Optional[date] = None
    interval_months: Optional[int] = 3
    status: str = "Aman"
    notes: Optional[str] = None


class MaintenanceCreate(MaintenanceBase):
    pass


class MaintenanceUpdate(BaseModel):
    asset_id: Optional[int] = None
    task_type: Optional[str] = None
    location_target: Optional[str] = None
    last_maintenance_date: Optional[date] = None
    next_schedule_date: Optional[date] = None
    interval_months: Optional[int] = None
    status: Optional[str] = None
    notes: Optional[str] = None


class MaintenanceResponse(MaintenanceBase):
    id: int

    model_config = {"from_attributes": True}
