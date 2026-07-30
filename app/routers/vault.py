from typing import List
from fastapi import APIRouter, Depends, status, Request

from app.core.deps import DbSession, CurrentUser, require_staff_or_admin, get_audit_logger
from app.models.schemas.credential import CredentialResponse, CredentialCreate, CredentialUpdate
from app.services import vault_service

router = APIRouter(prefix="/api/vault", tags=["Credential Vault"])

# 1. READ: Semua user yang login boleh melihat meta data kredensial (tanpa password)
@router.get("/", response_model=List[CredentialResponse])
def read_credentials(db: DbSession, current_user: CurrentUser):
    return vault_service.get_all_credentials(db)

# 2. CREATE: Dibatasi dan dilacak (Solusi Kerentanan #1)
@router.post("/", response_model=CredentialResponse, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_staff_or_admin), Depends(get_audit_logger)])
def create_credential(cred_data: CredentialCreate, db: DbSession):
    return vault_service.create_credential(db, cred_data)

# 3. UPDATE: Dibatasi dan dilacak (Solusi Kerentanan #1 & Bug #4)
@router.put("/{cred_id}", response_model=CredentialResponse, dependencies=[Depends(require_staff_or_admin), Depends(get_audit_logger)])
def update_credential(cred_id: int, cred_data: CredentialUpdate, db: DbSession):
    return vault_service.update_credential(db, cred_id, cred_data)

# 4. DELETE: Dibatasi dan dilacak (Solusi Kerentanan #1)
@router.delete("/{cred_id}", dependencies=[Depends(require_staff_or_admin), Depends(get_audit_logger)])
def delete_credential(cred_id: int, db: DbSession):
    return vault_service.delete_credential(db, cred_id)

# 5. REVEAL PASSWORD: Dibatasi khusus Admin/Staff IT & Wajib Catat Log (Solusi Kerentanan #6)
@router.get("/reveal/{cred_id}", dependencies=[Depends(require_staff_or_admin)])
def reveal_password(cred_id: int, request: Request, current_user: CurrentUser, db: DbSession):
    # Mengambil IP Address Client secara eksplisit untuk dikirim ke Service (Audit Trail)
    client_ip = request.client.host if request.client else "Unknown"
    return vault_service.reveal_password(db, cred_id, current_user.id, client_ip)
