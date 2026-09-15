from typing import List, Optional
from fastapi import APIRouter, Depends, File, UploadFile, status

from app.core.deps import CurrentUser, DbSession, get_audit_logger, require_staff_or_admin
from app.models.schemas.component import ComponentCreate, ComponentResponse, ComponentUpdate
from app.services import asset_service

router = APIRouter(prefix="/api/components", tags=["Components"])


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
