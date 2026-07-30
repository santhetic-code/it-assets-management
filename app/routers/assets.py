from typing import List
from fastapi import APIRouter, Depends, status

from app.core.deps import DbSession, CurrentUser, require_staff_or_admin, get_audit_logger
from app.services import asset_service

from app.models.schemas.asset import AssetResponse, AssetCreate, AssetUpdate
from app.models.schemas.component import ComponentResponse, ComponentCreate
from app.models.schemas.purchase import PurchaseResponse, PurchaseCreate
from app.models.schemas.maintenance import MaintenanceResponse, MaintenanceCreate

router = APIRouter(tags=["Asset Ecosystem"])

# ==========================================
# ENDPOINT ASET
# ==========================================
@router.get("/api/assets", response_model=List[AssetResponse])
def read_assets(db: DbSession, current_user: CurrentUser):
    return asset_service.get_all_assets(db)

@router.post("/api/assets", response_model=AssetResponse, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_staff_or_admin), Depends(get_audit_logger)])
def create_asset(asset_data: AssetCreate, db: DbSession):
    return asset_service.create_asset(db, asset_data)

@router.put("/api/assets/{asset_id}", response_model=AssetResponse, dependencies=[Depends(require_staff_or_admin), Depends(get_audit_logger)])
def update_asset(asset_id: int, asset_data: AssetUpdate, db: DbSession):
    return asset_service.update_asset(db, asset_id, asset_data)

@router.delete("/api/assets/{asset_id}", dependencies=[Depends(require_staff_or_admin), Depends(get_audit_logger)])
def delete_asset(asset_id: int, db: DbSession):
    return asset_service.delete_asset(db, asset_id)

# ==========================================
# ENDPOINT KOMPONEN, PEMBELIAN, MAINTENANCE
# ==========================================
# (Hanya rute dasar untuk mempersingkat, dilindungi secara ketat)

@router.get("/api/components", response_model=List[ComponentResponse])
def read_components(db: DbSession, current_user: CurrentUser):
    return asset_service.get_components(db)

@router.post("/api/components", response_model=ComponentResponse, dependencies=[Depends(require_staff_or_admin), Depends(get_audit_logger)])
def create_component(data: ComponentCreate, db: DbSession):
    return asset_service.create_component(db, data)

@router.get("/api/purchases", response_model=List[PurchaseResponse])
def read_purchases(db: DbSession, current_user: CurrentUser):
    return asset_service.get_purchases(db)

@router.post("/api/purchases", response_model=PurchaseResponse, dependencies=[Depends(require_staff_or_admin), Depends(get_audit_logger)])
def create_purchase(data: PurchaseCreate, db: DbSession):
    return asset_service.create_purchase(db, data)

@router.get("/api/maintenance", response_model=List[MaintenanceResponse])
def read_maintenance(db: DbSession, current_user: CurrentUser):
    return asset_service.get_all_maintenance(db)

@router.post("/api/maintenance", response_model=MaintenanceResponse, dependencies=[Depends(require_staff_or_admin), Depends(get_audit_logger)])
def create_maintenance(data: MaintenanceCreate, db: DbSession):
    return asset_service.create_maintenance(db, data)
