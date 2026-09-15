import os
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, File, Form, UploadFile, status

from app.core.deps import CurrentUser, DbSession, get_audit_logger, require_staff_or_admin
from app.core.security import secure_save_file
from app.models.schemas.purchase import PurchaseCreate, PurchaseResponse, PurchaseUpdate
from app.services import asset_service

router = APIRouter(prefix="/api/purchases", tags=["Purchases"])


@router.get("/", response_model=List[PurchaseResponse])
@router.get("", response_model=List[PurchaseResponse])
def read_purchases(db: DbSession, current_user: CurrentUser):
    return asset_service.get_purchases(db)


@router.post(
    "",
    response_model=PurchaseResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_staff_or_admin), Depends(get_audit_logger)],
)
@router.post(
    "/",
    response_model=PurchaseResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_staff_or_admin), Depends(get_audit_logger)],
)
async def create_purchase(
    db: DbSession,
    item_name: Optional[str] = Form(None),
    vendor: Optional[str] = Form(None),
    price_per_item: Optional[float] = Form(0.0),
    quantity: Optional[int] = Form(1),
    purchase_date: Optional[str] = Form(None),
    buyer_name: Optional[str] = Form(None),
    invoice_link: Optional[str] = Form(None),
    asset_id: Optional[str] = Form(None),
    nota_file: Optional[UploadFile] = File(None),
):
    parsed_asset_id = int(asset_id) if asset_id and str(asset_id).isdigit() else None
    parsed_date = None
    if purchase_date:
        try:
            parsed_date = datetime.strptime(purchase_date, "%Y-%m-%d").date()
        except ValueError:
            parsed_date = None

    uploaded_file_path = None
    if nota_file and nota_file.filename:
        os.makedirs(os.path.join("static", "uploads"), exist_ok=True)
        safe_name = f"nota_{int(datetime.now().timestamp())}_{nota_file.filename}"
        dest_path = os.path.join("static", "uploads", safe_name)
        await secure_save_file(nota_file, dest_path)
        uploaded_file_path = f"/static/uploads/{safe_name}"

    unit_price = float(price_per_item or 0.0)
    qty = int(quantity or 1)
    tot_price = unit_price * qty
    final_invoice_link = invoice_link or uploaded_file_path

    purchase_in = PurchaseCreate(
        asset_id=parsed_asset_id,
        item_name=item_name,
        vendor=vendor,
        purchase_date=parsed_date,
        price_per_item=unit_price,
        quantity=qty,
        cost=unit_price,
        total_price=tot_price,
        buyer_name=buyer_name,
        invoice_link=final_invoice_link,
        nota_file=uploaded_file_path,
    )
    return asset_service.create_purchase(db, purchase_in)


@router.put(
    "/{purchase_id}",
    response_model=PurchaseResponse,
    dependencies=[Depends(require_staff_or_admin), Depends(get_audit_logger)],
)
def update_purchase(purchase_id: int, data: PurchaseUpdate, db: DbSession):
    return asset_service.update_purchase(db, purchase_id, data)


@router.delete(
    "/{purchase_id}",
    dependencies=[Depends(require_staff_or_admin), Depends(get_audit_logger)],
)
def delete_purchase(purchase_id: int, db: DbSession):
    return asset_service.delete_purchase(db, purchase_id)
