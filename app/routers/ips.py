from typing import List
from fastapi import APIRouter, Depends, status

from app.core.deps import DbSession, CurrentUser, require_staff_or_admin, get_audit_logger
from app.models.schemas.network_ip import NetworkIPResponse, NetworkIPCreate, NetworkIPUpdate
from app.services import ip_service

# Membuat router khusus untuk entitas IP
router = APIRouter(prefix="/api/ips", tags=["Network IPs"])

# 1. READ: Semua user yang berhasil login boleh melihat data IP
@router.get("/", response_model=List[NetworkIPResponse])
def read_ips(db: DbSession, current_user: CurrentUser):
    return ip_service.get_all_ips(db)

# 2. CREATE: Hanya Staff/Admin, sekaligus memperbaiki BUG #2 (Endpoint POST yang hilang)
@router.post("/", response_model=NetworkIPResponse, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_staff_or_admin), Depends(get_audit_logger)])
def create_ip(ip_data: NetworkIPCreate, db: DbSession):
    return ip_service.create_ip(db, ip_data)

# 3. UPDATE: Hanya Staff/Admin, sekaligus memperbaiki BUG #2 (Endpoint PUT yang hilang)
@router.put("/{ip_id}", response_model=NetworkIPResponse, dependencies=[Depends(require_staff_or_admin), Depends(get_audit_logger)])
def update_ip(ip_id: int, ip_data: NetworkIPUpdate, db: DbSession):
    return ip_service.update_ip(db, ip_id, ip_data)

# 4. DELETE: Hanya Staff/Admin, menutup celah keamanan
@router.delete("/{ip_id}", dependencies=[Depends(require_staff_or_admin), Depends(get_audit_logger)])
def delete_ip(ip_id: int, db: DbSession):
    return ip_service.delete_ip(db, ip_id)
