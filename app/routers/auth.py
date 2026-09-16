from typing import List
from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import CurrentUser, DbSession, get_audit_logger, require_super_admin
from app.core.security import create_access_token, verify_password
from app.models.domain import User
from app.models.schemas.user import UserCreate, UserResponse, UserUpdate
from app.services import auth_service

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


# Menggunakan JSON Model murni agar lebih tangguh
class LoginRequest(BaseModel):
    username: str
    password: str


@router.post("/login")
def login(request_data: LoginRequest, response: Response, db: Session = Depends(get_db)):
    # 1. Cari user di database
    user = db.query(User).filter(User.username == request_data.username).first()

    # 2. Validasi User & Password
    if not user or not verify_password(request_data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Username atau sandi salah!")

    # 3. Validasi Akun (Jika NULL di database, kita anggap tetap Aktif)
    if user.is_active is False or user.is_active == 0:
        raise HTTPException(status_code=403, detail="Akun Anda sedang dinonaktifkan.")

    # 4. Buat Tiket JWT (Toleransi jika full_name kosong)
    nama_tampil = user.full_name if user.full_name else user.username
    role_tampil = user.role if user.role else "Staff IT"

    access_token = create_access_token(
        data={"sub": user.username, "role": role_tampil, "name": nama_tampil}
    )

    # 5. Tanamkan Tiket ke Browser (HTTPOnly)
    response.set_cookie(
        key="access_token",
        value=f"Bearer {access_token}",
        httponly=True,
        max_age=7200,
        expires=7200,
    )
    # Dukungan backward-compatibility untuk itam_session
    response.set_cookie(
        key="itam_session",
        value=access_token,
        httponly=True,
        max_age=7200,
        expires=7200,
    )

    return {"message": "Berhasil Login", "name": nama_tampil, "role": role_tampil}


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie("access_token")
    response.delete_cookie("itam_session")
    return {"message": "Berhasil Logout"}


# ==========================================
# USER MANAGEMENT (KHUSUS SUPER ADMIN)
# ==========================================
@router.get(
    "/users",
    response_model=List[UserResponse],
    dependencies=[Depends(require_super_admin)],
)
def read_users(db: DbSession):
    return auth_service.get_all_users(db)


@router.post(
    "/users",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_super_admin), Depends(get_audit_logger)],
)
def create_user(user_data: UserCreate, db: DbSession):
    return auth_service.create_user(db, user_data)


@router.put(
    "/users/{user_id}",
    response_model=UserResponse,
    dependencies=[Depends(require_super_admin), Depends(get_audit_logger)],
)
def update_user(user_id: int, user_data: UserUpdate, db: DbSession):
    return auth_service.update_user(db, user_id, user_data)


@router.delete(
    "/users/{user_id}",
    dependencies=[Depends(require_super_admin), Depends(get_audit_logger)],
)
def delete_user(user_id: int, current_user: CurrentUser, db: DbSession):
    return auth_service.delete_user(db, user_id, current_user.id)
