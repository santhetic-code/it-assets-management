import io
import os
from datetime import datetime
from typing import List, Optional

import qrcode
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, Response, UploadFile, status
from fastapi.responses import StreamingResponse

from app.core.deps import CurrentUser, DbSession, get_audit_logger, require_staff_or_admin
from app.core.security import secure_save_file
from app.models.schemas.asset import AssetCreate, AssetResponse, AssetUpdate
from app.models.schemas.component import ComponentCreate, ComponentResponse, ComponentUpdate
from app.models.schemas.maintenance import MaintenanceCreate, MaintenanceResponse, MaintenanceUpdate
from app.models.schemas.purchase import PurchaseCreate, PurchaseResponse, PurchaseUpdate
from app.services import asset_service

router = APIRouter(tags=["Asset Ecosystem"])

# ==========================================
# 1. ENDPOINT ASET
# ==========================================
@router.get("/api/assets", response_model=List[AssetResponse])
def read_assets(db: DbSession, current_user: CurrentUser):
    return asset_service.get_all_assets(db)


@router.post(
    "/api/assets",
    response_model=AssetResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_staff_or_admin), Depends(get_audit_logger)],
)
def create_asset(asset_data: AssetCreate, db: DbSession):
    return asset_service.create_asset(db, asset_data)


@router.put(
    "/api/assets/{asset_id}",
    response_model=AssetResponse,
    dependencies=[Depends(require_staff_or_admin), Depends(get_audit_logger)],
)
def update_asset(asset_id: int, asset_data: AssetUpdate, db: DbSession):
    return asset_service.update_asset(db, asset_id, asset_data)


@router.delete(
    "/api/assets/{asset_id}",
    dependencies=[Depends(require_staff_or_admin), Depends(get_audit_logger)],
)
def delete_asset(asset_id: int, db: DbSession):
    return asset_service.delete_asset(db, asset_id)


@router.post(
    "/api/assets/import",
    dependencies=[Depends(require_staff_or_admin), Depends(get_audit_logger)],
)
async def import_assets(file: UploadFile = File(...), db: DbSession = None):
    contents = await file.read()
    count = asset_service.import_assets_from_file(db, contents, file.filename)
    return {"message": f"Berhasil mengimpor {count} data aset.", "count": count}


@router.get("/api/qr/{asset_tag}")
def generate_qr(asset_tag: str):
    qr = qrcode.QRCode(
        version=1,
        box_size=10,
        border=2,
    )
    qr.add_data(asset_tag)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format="PNG")
    img_byte_arr.seek(0)
    return StreamingResponse(img_byte_arr, media_type="image/png")


# ==========================================
# 2. ENDPOINT KOMPONEN
# ==========================================
@router.get("/api/components", response_model=List[ComponentResponse])
def read_components(db: DbSession, current_user: CurrentUser):
    return asset_service.get_components(db)


@router.post(
    "/api/components",
    response_model=ComponentResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_staff_or_admin), Depends(get_audit_logger)],
)
def create_component(data: ComponentCreate, db: DbSession):
    return asset_service.create_component(db, data)


@router.put(
    "/api/components/{component_id}",
    response_model=ComponentResponse,
    dependencies=[Depends(require_staff_or_admin), Depends(get_audit_logger)],
)
def update_component(component_id: int, data: ComponentUpdate, db: DbSession):
    return asset_service.update_component(db, component_id, data)


@router.delete(
    "/api/components/{component_id}",
    dependencies=[Depends(require_staff_or_admin), Depends(get_audit_logger)],
)
def delete_component(component_id: int, db: DbSession):
    return asset_service.delete_component(db, component_id)


# ==========================================
# 3. ENDPOINT PEMBELIAN (Form-Data & File Upload)
# ==========================================
@router.get("/api/purchases", response_model=List[PurchaseResponse])
def read_purchases(db: DbSession, current_user: CurrentUser):
    return asset_service.get_purchases(db)


@router.post(
    "/api/purchases",
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
    "/api/purchases/{purchase_id}",
    response_model=PurchaseResponse,
    dependencies=[Depends(require_staff_or_admin), Depends(get_audit_logger)],
)
def update_purchase(purchase_id: int, data: PurchaseUpdate, db: DbSession):
    return asset_service.update_purchase(db, purchase_id, data)


@router.delete(
    "/api/purchases/{purchase_id}",
    dependencies=[Depends(require_staff_or_admin), Depends(get_audit_logger)],
)
def delete_purchase(purchase_id: int, db: DbSession):
    return asset_service.delete_purchase(db, purchase_id)


# ==========================================
# 4. ENDPOINT MAINTENANCE
# ==========================================
@router.get("/api/maintenance", response_model=List[MaintenanceResponse])
def read_maintenance(db: DbSession, current_user: CurrentUser):
    return asset_service.get_all_maintenance(db)


@router.post(
    "/api/maintenance",
    response_model=MaintenanceResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_staff_or_admin), Depends(get_audit_logger)],
)
def create_maintenance(data: MaintenanceCreate, db: DbSession):
    return asset_service.create_maintenance(db, data)


@router.put(
    "/api/maintenance/{maintenance_id}",
    response_model=MaintenanceResponse,
    dependencies=[Depends(require_staff_or_admin), Depends(get_audit_logger)],
)
def update_maintenance(maintenance_id: int, data: MaintenanceUpdate, db: DbSession):
    return asset_service.update_maintenance(db, maintenance_id, data)


@router.delete(
    "/api/maintenance/{maintenance_id}",
    dependencies=[Depends(require_staff_or_admin), Depends(get_audit_logger)],
)
def delete_maintenance(maintenance_id: int, db: DbSession):
    return asset_service.delete_maintenance(db, maintenance_id)
