from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel


class PurchaseBase(BaseModel):
    item_name: str
    vendor: Optional[str] = None
    unit_price: Decimal
    quantity: int = 1
    total_price: Decimal
    purchase_date: date
    category: Optional[str] = None
    description: Optional[str] = None


class PurchaseCreate(PurchaseBase):
    pass  # file_path di-handle terpisah oleh endpoint upload


class PurchaseUpdate(BaseModel):
    item_name: Optional[str] = None
    vendor: Optional[str] = None
    unit_price: Optional[Decimal] = None
    quantity: Optional[int] = None
    total_price: Optional[Decimal] = None
    purchase_date: Optional[date] = None
    category: Optional[str] = None
    description: Optional[str] = None
    file_path: Optional[str] = None


class PurchaseResponse(PurchaseBase):
    id: int
    file_path: Optional[str] = None
    created_at: Optional[datetime] = None
    created_by: Optional[int] = None

    model_config = {"from_attributes": True}
