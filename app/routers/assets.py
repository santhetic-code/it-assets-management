from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_audit_logger, require_staff_or_admin, require_super_admin
from app.models.schemas.asset import AssetCreate, AssetResponse, AssetUpdate
from app.services import asset_service

router = APIRouter(prefix="/api/assets", tags=["Assets"])


@router.get("/", response_model=List[AssetResponse])
@router.get("", response_model=List[AssetResponse])
def read_assets(skip: int = 0, limit: int = 1000, db: Session = Depends(get_db)):
    assets = asset_service.get_assets(db, skip=skip, limit=limit)
    return assets


@router.post("/", response_model=AssetResponse, dependencies=[Depends(require_staff_or_admin)])
@router.post("", response_model=AssetResponse, dependencies=[Depends(require_staff_or_admin)])
def create_asset(asset: AssetCreate, db: Session = Depends(get_db)):
    return asset_service.create_asset(db=db, asset=asset)


@router.put("/{asset_id}", response_model=AssetResponse, dependencies=[Depends(require_staff_or_admin)])
def update_asset(asset_id: int, asset: AssetUpdate, db: Session = Depends(get_db)):
    db_asset = asset_service.update_asset(db, asset_id, asset)
    if not db_asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    return db_asset


# HANYA SUPER ADMIN YANG BOLEH MENGHAPUS ASET (SOFT DELETE)
@router.delete("/{asset_id}", dependencies=[Depends(require_super_admin)])
def delete_asset(
    asset_id: int,
    db: Session = Depends(get_db),
    audit_info: dict = Depends(get_audit_logger),
):
    success = asset_service.delete_asset(
        db,
        asset_id,
        user_id=audit_info["user_id"],
        client_ip=audit_info["ip"],
    )
    if not success:
        raise HTTPException(status_code=404, detail="Asset not found")
    return {"detail": "Asset berhasil dinonaktifkan (Soft Delete) dan dicatat di Audit Trail"}
