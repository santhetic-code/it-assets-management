from typing import Optional
from datetime import date
from pydantic import BaseModel

class PurchaseBase(BaseModel):
    asset_id: int
    vendor: Optional[str] = None
    purchase_date: Optional[date] = None
    cost: float = 0.0
    total_price: float = 0.0

class PurchaseCreate(PurchaseBase):
    pass

class PurchaseUpdate(BaseModel):
    vendor: Optional[str] = None
    purchase_date: Optional[date] = None
    cost: Optional[float] = None
    total_price: Optional[float] = None

class PurchaseResponse(PurchaseBase):
    id: int

    model_config = {"from_attributes": True}
