from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.core.database import get_db
from app.models.schemas.credential import VaultCreate, VaultUpdate, VaultResponse
from app.services import vault_service

# Prefix ini berarti semua URL di file ini akan diawali dengan /api/vault
router = APIRouter(prefix="/api/vault", tags=["Vault"])

@router.get("/", response_model=List[VaultResponse])
def read_vaults(db: Session = Depends(get_db)):
    return vault_service.get_vaults(db)

@router.post("/", response_model=VaultResponse)
def create_vault(vault: VaultCreate, db: Session = Depends(get_db)):
    return vault_service.create_vault(db=db, vault=vault)

@router.put("/{vault_id}", response_model=VaultResponse)
def update_vault(vault_id: int, vault: VaultUpdate, db: Session = Depends(get_db)):
    db_vault = vault_service.update_vault(db, vault_id, vault)
    if not db_vault:
        raise HTTPException(status_code=404, detail="Kredensial tidak ditemukan")
    return db_vault

@router.delete("/{vault_id}")
def delete_vault(vault_id: int, db: Session = Depends(get_db)):
    success = vault_service.delete_vault(db, vault_id)
    if not success:
        raise HTTPException(status_code=404, detail="Kredensial tidak ditemukan")
    return {"detail": "Data Vault berhasil dihapus"}
