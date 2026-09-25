from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.security import verify_csrf_token
from app.models.schemas.component import ComponentCreate, ComponentUpdate, ComponentResponse, ComponentHistoryResponse
from app.services import component_service

router = APIRouter(prefix="/api/components", tags=["Components"])
master_router = APIRouter(prefix="/api/master-components", tags=["Master Components"])


@router.get("", response_model=List[ComponentResponse])
@router.get("/", response_model=List[ComponentResponse])
def read_components(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """Mengambil daftar semua spesifikasi PC (komponen) aktif."""
    return component_service.get_components(db, skip=skip, limit=limit)


@router.get("/{component_id}", response_model=ComponentResponse)
def read_component(component_id: int, db: Session = Depends(get_db)):
    """Mengambil detail spesifikasi PC berdasarkan ID."""
    db_component = component_service.get_component(db, component_id=component_id)
    if db_component is None:
        raise HTTPException(status_code=404, detail="Komponen tidak ditemukan")
    return db_component


@router.post("", response_model=ComponentResponse, status_code=status.HTTP_201_CREATED, dependencies=[Depends(verify_csrf_token)])
@router.post("/", response_model=ComponentResponse, status_code=status.HTTP_201_CREATED, dependencies=[Depends(verify_csrf_token)])
def create_component(
    component: ComponentCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    """Mendaftarkan spesifikasi PC baru."""
    return component_service.create_component(db=db, component=component, current_user_id=current_user.id)


@router.put("/{component_id}", response_model=ComponentResponse, dependencies=[Depends(verify_csrf_token)])
def update_component(
    component_id: int,
    component: ComponentUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    """Memperbarui spesifikasi PC."""
    db_component = component_service.update_component(db, component_id=component_id, component_data=component, current_user_id=current_user.id)
    if db_component is None:
        raise HTTPException(status_code=404, detail="Komponen tidak ditemukan")
    return db_component


@router.delete("/{component_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(verify_csrf_token)])
def delete_component(
    component_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    """Menghapus (Soft Delete) spesifikasi PC."""
    db_component = component_service.delete_component(db, component_id=component_id, current_user_id=current_user.id)
    if db_component is None:
        raise HTTPException(status_code=404, detail="Komponen tidak ditemukan")
    return None


@router.get("/{component_id}/history", response_model=List[ComponentHistoryResponse])
def get_component_history(component_id: int, db: Session = Depends(get_db)):
    """Mengambil riwayat perubahan (Audit Trail) dari sebuah spesifikasi PC."""
    history = component_service.get_component_history(db, component_id)
    if not history:
        raise HTTPException(status_code=404, detail="Riwayat komponen tidak ditemukan")
    return history
