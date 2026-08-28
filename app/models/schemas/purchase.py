from datetime import date
from typing import Optional
from pydantic import BaseModel


class PurchaseBase(BaseModel):
    asset_id: Optional[int] = None
    item_name: Optional[str] = None
    vendor: Optional[str] = None
    purchase_date: Optional[date] = None
    price_per_item: float = 0.0
    quantity: int = 1
    cost: float = 0.0
    total_price: float = 0.0
    buyer_name: Optional[str] = None
    invoice_link: Optional[str] = None
    nota_file: Optional[str] = None


class PurchaseCreate(PurchaseBase):
    pass


class PurchaseUpdate(BaseModel):
    asset_id: Optional[int] = None
    item_name: Optional[str] = None
    vendor: Optional[str] = None
    purchase_date: Optional[date] = None
    price_per_item: Optional[float] = None
    quantity: Optional[int] = None
    cost: Optional[float] = None
    total_price: Optional[float] = None
    buyer_name: Optional[str] = None
    invoice_link: Optional[str] = None
    nota_file: Optional[str] = None


class PurchaseResponse(PurchaseBase):
    id: int

    model_config = {"from_attributes": True}
