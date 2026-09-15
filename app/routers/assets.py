from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.schemas.asset import AssetCreate, AssetResponse, AssetUpdate
from app.services import asset_service

router = APIRouter(prefix="/api/assets", tags=["Assets"])


@router.get("/", response_model=List[AssetResponse])
@router.get("", response_model=List[AssetResponse])
def read_assets(skip: int = 0, limit: int = 1000, db: Session = Depends(get_db)):
    assets = asset_service.get_assets(db, skip=skip, limit=limit)
    return assets


@router.post("/", response_model=AssetResponse)
@router.post("", response_model=AssetResponse)
def create_asset(asset: AssetCreate, db: Session = Depends(get_db)):
    return asset_service.create_asset(db=db, asset=asset)


@router.put("/{asset_id}", response_model=AssetResponse)
def update_asset(asset_id: int, asset: AssetUpdate, db: Session = Depends(get_db)):
    db_asset = asset_service.update_asset(db, asset_id, asset)
    if not db_asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    return db_asset


@router.delete("/{asset_id}")
def delete_asset(asset_id: int, db: Session = Depends(get_db)):
    success = asset_service.delete_asset(db, asset_id)
    if not success:
        raise HTTPException(status_code=404, detail="Asset not found")
    return {"detail": "Asset deleted successfully"}
