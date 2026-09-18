from typing import List, Optional
from fastapi import APIRouter, Depends, File, UploadFile, status

from app.core.deps import CurrentUser, DbSession, get_audit_logger, require_staff_or_admin
from app.models.schemas.component import (
    ComponentCreate,
    ComponentResponse,
    ComponentUpdate,
    ComponentCreateV2,
    ComponentUpdateV2,
    ComponentResponseV2,
    ComponentHistoryResponse,
    MasterComponentCreate,
    MasterComponentResponse,
)
from app.services import asset_service
from app.services import component_service

router = APIRouter(prefix="/api/components", tags=["Components"])


# ==========================================
# ENDPOINT LAMA (DIPERTAHANKAN — free-text)
# ==========================================

@router.get("/", response_model=List[ComponentResponse])
@router.get("", response_model=List[ComponentResponse])
def read_components(
    db: DbSession, current_user: CurrentUser, pc_type: Optional[str] = None
):
    return asset_service.get_components(db, pc_type=pc_type)


@router.post(
    "",
    response_model=ComponentResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_staff_or_admin), Depends(get_audit_logger)],
)
@router.post(
    "/",
    response_model=ComponentResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_staff_or_admin), Depends(get_audit_logger)],
)
def create_component(data: ComponentCreate, db: DbSession):
    return asset_service.create_component(db, data)


@router.put(
    "/{component_id}",
    response_model=ComponentResponse,
    dependencies=[Depends(require_staff_or_admin), Depends(get_audit_logger)],
)
def update_component(component_id: int, data: ComponentUpdate, db: DbSession):
    return asset_service.update_component(db, component_id, data)


@router.delete(
    "/{component_id}",
    dependencies=[Depends(require_staff_or_admin), Depends(get_audit_logger)],
)
def delete_component(component_id: int, db: DbSession):
    return asset_service.delete_component(db, component_id)


@router.post(
    "/import",
    dependencies=[Depends(require_staff_or_admin), Depends(get_audit_logger)],
)
async def import_components_endpoint(
    file: UploadFile = File(...),
    db: DbSession = None,
):
    result = await asset_service.import_components_from_file(db, file)
    return result


# ==========================================
# MASTER COMPONENT CRUD (Dropdown Reference)
# ==========================================

@router.get("/masters", response_model=List[MasterComponentResponse], tags=["Master Data"])
def list_master_components(
    db: DbSession,
    current_user: CurrentUser,
    category: Optional[str] = None,
):
    """Ambil semua master komponen, opsional filter berdasarkan kategori (CPU, RAM, dll.)."""
    return component_service.get_all_masters(db, category=category)


@router.post(
    "/masters",
    response_model=MasterComponentResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_staff_or_admin)],
    tags=["Master Data"],
)
def create_master_component(data: MasterComponentCreate, db: DbSession):
    """Tambah entri baru ke master data komponen (untuk mengisi dropdown)."""
    return component_service.create_master(db, data)


@router.delete(
    "/masters/{master_id}",
    dependencies=[Depends(require_staff_or_admin)],
    tags=["Master Data"],
)
def delete_master_component(master_id: int, db: DbSession):
    """Hapus entri dari master data komponen."""
    return component_service.delete_master(db, master_id)


# ==========================================
# COMPONENT v2 — FK-based dengan Auto-Diff
# ==========================================

@router.get(
    "/v2/by-asset/{asset_id}",
    response_model=ComponentResponseV2,
    tags=["Components v2"],
)
def get_component_by_asset(asset_id: int, db: DbSession, current_user: CurrentUser):
    """Ambil spesifikasi PC berdasarkan asset_id."""
    comp = component_service.get_component_by_asset(db, asset_id)
    if not comp:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Spesifikasi PC belum didaftarkan untuk aset ini.")
    return comp


@router.post(
    "/v2",
    response_model=ComponentResponseV2,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_staff_or_admin)],
    tags=["Components v2"],
)
def create_component_v2(data: ComponentCreateV2, db: DbSession, current_user: CurrentUser):
    """
    Daftarkan spesifikasi PC baru menggunakan ID dari master_components.
    Auto-mencatat CREATE ke ComponentHistory.
    """
    return component_service.create_component_v2(db, data, user_id=current_user.id)


@router.put(
    "/v2/{component_id}",
    response_model=ComponentResponseV2,
    dependencies=[Depends(require_staff_or_admin)],
    tags=["Components v2"],
)
def update_component_v2(
    component_id: int,
    data: ComponentUpdateV2,
    db: DbSession,
    current_user: CurrentUser,
):
    """
    Kemaskini spesifikasi PC dengan AUTO-DIFF ENGINE.
    Sistem mengesan perubahan secara automatik dan mencatat ke ComponentHistory
    tanpa staf IT perlu menaip log secara manual.
    """
    return component_service.update_component_v2(db, component_id, data, user_id=current_user.id)


@router.get(
    "/v2/{component_id}/history",
    response_model=List[ComponentHistoryResponse],
    tags=["Components v2"],
)
def get_component_history(
    component_id: int, db: DbSession, current_user: CurrentUser
):
    """Ambil audit trail lengkap untuk satu rekod spesifikasi PC."""
    return component_service.get_component_history(db, component_id)
