from typing import Any, Dict, List, Optional, Union
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import func

from app.core.deps import (
    CurrentUser,
    DbSession,
    get_audit_logger,
    require_staff_or_admin,
    require_super_admin,
)
from app.models import domain
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
master_router = APIRouter(prefix="/api/master-components", tags=["Master Components"])


@master_router.get("")
@master_router.get("/")
def read_master_components_grouped(
    db: DbSession,
    current_user: CurrentUser,
    category: Optional[str] = None,
):
    """Endpoint untuk pemanggilan AJAX Master Components yang mengembalikan envelope { data: [...] }."""
    masters = component_service.get_all_masters(db, category=category)
    return {
        "data": [
            {
                "id": m.id,
                "name": m.name,
                "category": m.category,
                "description": m.description,
            }
            for m in masters
        ]
    }


# ==========================================
# ENDPOINT AUTOCOMPLETE SUGGESTIONS
# ==========================================

@router.get("/suggestions")
def get_component_suggestions(
    field: str,
    db: DbSession,
    current_user: CurrentUser,
):
    """
    Mengambil daftar unik saran autocomplete (datalist) untuk satu jenis field komponen
    (cpu, mainboard, ram, storage, vga, os, monitor, keyboard, mouse)
    berdasarkan data historis komponen dan master components.
    """
    field_lower = field.lower().strip()
    field_map = {
        "cpu": (domain.Component.processor_spec, "CPU"),
        "mainboard": (domain.Component.mainboard_spec, "Mainboard"),
        "ram": (domain.Component.ram_spec, "RAM"),
        "storage": (domain.Component.storage_spec, "Storage"),
        "vga": (domain.Component.vga_spec, "VGA"),
        "os": (domain.Component.os_name, "OS"),
        "monitor": (domain.Component.monitor, "Monitor"),
        "keyboard": (domain.Component.keyboard, "Keyboard"),
        "mouse": (domain.Component.mouse, "Mouse"),
    }

    if field_lower not in field_map:
        return {"data": []}

    col, cat = field_map[field_lower]

    # Ambil nilai distinct dari tabel components
    comp_rows = (
        db.query(col)
        .filter(col.isnot(None), col != "", col != "-")
        .distinct()
        .all()
    )
    comp_vals = [r[0] for r in comp_rows if r[0]]

    # Ambil nilai dari master_components jika kategorinya ada
    master_vals = []
    if cat:
        master_rows = (
            db.query(domain.MasterComponent.name)
            .filter(func.lower(domain.MasterComponent.category) == func.lower(cat))
            .all()
        )
        master_vals = [r[0] for r in master_rows if r[0]]

    # Gabung dan bersihkan duplikat
    combined = set()
    for item in comp_vals + master_vals:
        clean = (item or "").strip()
        if clean and clean != "-":
            combined.add(clean)

    return {"data": sorted(list(combined))}


# ==========================================
# ENDPOINT LAMA & HYBRID (DIPERTAHANKAN)
# ==========================================

@router.get("/", response_model=Dict[str, Any])
@router.get("", response_model=Dict[str, Any])
def read_components(
    db: DbSession, current_user: CurrentUser, pc_type: Optional[str] = None
):
    comps = asset_service.get_components(db, pc_type=pc_type)
    return {
        "data": [
            ComponentResponse.model_validate(c).model_dump()
            for c in comps
        ]
    }


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_staff_or_admin), Depends(get_audit_logger)],
)
@router.post(
    "/",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_staff_or_admin), Depends(get_audit_logger)],
)
def create_component(
    data: Union[ComponentCreateV2, ComponentCreate],
    db: DbSession,
    current_user: CurrentUser,
):
    if isinstance(data, ComponentCreateV2):
        return component_service.create_component_v2(db, data, user_id=current_user.id)
    return asset_service.create_component(db, data)


@router.put(
    "/{component_id}",
    dependencies=[Depends(require_staff_or_admin), Depends(get_audit_logger)],
)
def update_component(
    component_id: int,
    data: Union[ComponentUpdateV2, ComponentUpdate],
    db: DbSession,
    current_user: CurrentUser,
):
    if isinstance(data, ComponentUpdateV2):
        return component_service.update_component_v2(db, component_id, data, user_id=current_user.id)
    return asset_service.update_component(db, component_id, data)


@router.delete(
    "/{component_id}",
    dependencies=[Depends(require_super_admin)],
)
def delete_component(
    component_id: int,
    db: DbSession,
    audit_info: dict = Depends(get_audit_logger),
):
    return component_service.soft_delete_component(
        db=db,
        component_id=component_id,
        user_id=audit_info["user_id"],
        client_ip=audit_info["ip"],
    )


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
    dependencies=[Depends(require_super_admin)],
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


@router.get(
    "/{component_id}",
    tags=["Components"],
)
@router.get(
    "/{component_id}/detail",
    tags=["Components"],
)
def get_component_detail(
    component_id: int, db: DbSession, current_user: CurrentUser
):
    """
    Ambil butiran penuh satu komponen PC beserta riwayat perubahannya (Audit History).
    Digunakan oleh Modal Detail dan Prefill Form Edit Offcanvas.
    """
    comp = db.query(domain.Component).filter(
        domain.Component.id == component_id,
        domain.Component.is_deleted == False
    ).first()
    if not comp:
        raise HTTPException(status_code=404, detail="Spesifikasi PC tidak ditemukan.")

    asset_name = comp.asset.nama if comp.asset else comp.name
    history = component_service.get_component_history(db, component_id)

    raw_monitor = comp.monitor if comp.monitor and comp.monitor != "-" else (comp.monitor_ref.name if comp.monitor_ref else None)
    raw_keyboard = comp.keyboard if comp.keyboard and comp.keyboard != "-" else None
    raw_mouse = comp.mouse if comp.mouse and comp.mouse != "-" else None

    return {
        "data": {
            "id": comp.id,
            "identitas_pc": comp.user_pc,
            "name": comp.name,
            "asset_id": comp.asset_id,
            "asset_name": asset_name,
            "jenis_pc": comp.jenis_pc,
            "cpu": comp.cpu if comp.cpu != "-" else "",
            "cpu_id": comp.cpu_id,
            "cpu_name": comp.cpu,
            "ram": comp.ram if comp.ram != "-" else "",
            "ram_id": comp.ram_id,
            "ram_name": comp.ram,
            "vga": comp.vga if comp.vga != "-" else "",
            "vga_id": comp.vga_id,
            "vga_name": comp.vga,
            "storage": comp.storage if comp.storage != "-" else "",
            "storage_id": comp.storage_id,
            "storage_name": comp.storage,
            "os": comp.os if comp.os != "-" else "",
            "os_id": comp.os_id,
            "os_name": comp.os,
            "mainboard": comp.mainboard if comp.mainboard != "-" else "",
            "mainboard_id": comp.mainboard_id,
            "mainboard_name": comp.mainboard,
            "monitor_id": comp.monitor_id,
            "monitor": raw_monitor,
            "keyboard": raw_keyboard,
            "mouse": raw_mouse,
        },
        "history": [
            {
                "id": h.id,
                "action_type": h.action_type,
                "user_name": (h.user.full_name or h.user.username) if h.user else "Sistem",
                "created_at": h.created_at.strftime("%d %b %Y %H:%M") if h.created_at else "-",
                "changes_detail": h.changes_detail,
            }
            for h in history
        ],
    }
