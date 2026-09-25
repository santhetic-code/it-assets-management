from typing import List
from fastapi import APIRouter, Depends, status

from app.core.deps import CurrentUser, DbSession, get_audit_logger, require_staff_or_admin
from app.core.security import verify_csrf_token
from app.models.schemas.maintenance import MaintenanceCreate, MaintenanceResponse, MaintenanceUpdate
from app.services import asset_service

router = APIRouter(prefix="/api/maintenance", tags=["Maintenance"])


@router.get("/", response_model=List[MaintenanceResponse])
@router.get("", response_model=List[MaintenanceResponse])
def read_maintenance(db: DbSession, current_user: CurrentUser):
    return asset_service.get_all_maintenance(db)


@router.post(
    "",
    response_model=MaintenanceResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_staff_or_admin), Depends(get_audit_logger), Depends(verify_csrf_token)],
)
@router.post(
    "/",
    response_model=MaintenanceResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_staff_or_admin), Depends(get_audit_logger), Depends(verify_csrf_token)],
)
def create_maintenance(data: MaintenanceCreate, db: DbSession):
    return asset_service.create_maintenance(db, data)


@router.put(
    "/{maintenance_id}",
    response_model=MaintenanceResponse,
    dependencies=[Depends(require_staff_or_admin), Depends(get_audit_logger), Depends(verify_csrf_token)],
)
def update_maintenance(maintenance_id: int, data: MaintenanceUpdate, db: DbSession):
    return asset_service.update_maintenance(db, maintenance_id, data)


@router.delete(
    "/{maintenance_id}",
    dependencies=[Depends(require_staff_or_admin), Depends(get_audit_logger), Depends(verify_csrf_token)],
)
def delete_maintenance(maintenance_id: int, db: DbSession):
    return asset_service.delete_maintenance(db, maintenance_id)

