import os
import shutil
from typing import List
from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import CurrentUser, DbSession, get_audit_logger, require_super_admin
from app.core.security import create_access_token, get_password_hash, verify_password
from app.models.domain import User
from app.models.schemas.user import UserCreate, UserResponse, UserUpdate
from app.services import auth_service

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


class NewUserRequest(BaseModel):
    username: str
    role: str
    password: str


class ChangePasswordRequest(BaseModel):
    username: str
    old_password: str
    new_password: str


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


# ==========================================
# API 1: TAMBAH PENGGUNA BARU
# ==========================================
@router.post("/users")
def create_new_user(data: NewUserRequest, db: Session = Depends(get_db)):
    # Cek apakah username sudah dipakai
    user_exist = db.query(User).filter(User.username == data.username).first()
    if user_exist:
        raise HTTPException(status_code=400, detail="Username sudah digunakan!")

    new_user = User(
        username=data.username,
        full_name=data.username,  # Default sama dengan username dulu
        role=data.role,
        password_hash=get_password_hash(data.password),
        is_active=True,
    )
    db.add(new_user)
    db.commit()
    return {"message": "Pengguna baru berhasil ditambahkan"}


@router.put(
    "/users/{user_id}",
    response_model=UserResponse,
    dependencies=[Depends(require_super_admin), Depends(get_audit_logger)],
)
def update_user(user_id: int, user_data: UserUpdate, db: DbSession):
    return auth_service.update_user(db, user_id, user_data)


@router.delete("/users/{user_id}")
def delete_user(user_id: int, db: Session = Depends(get_db)):
    # 1. Cari user di database berdasarkan ID
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(status_code=404, detail="Akun tidak ditemukan di sistem.")

    # 2. Keamanan ekstra: Cegah Super Admin menghapus dirinya sendiri
    if user.username == "developer":
        raise HTTPException(
            status_code=403,
            detail="Fatal Error: Akun utama/developer tidak boleh dihapus!",
        )

    # 3. Eksekusi hapus
    db.delete(user)
    db.commit()

    return {"message": f"Akun {user.username} berhasil dihapus permanen"}


# ==========================================
# API 2: GANTI KATA SANDI
# ==========================================
@router.put("/change-password")
def change_password(data: ChangePasswordRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == data.username).first()

    if not user or not verify_password(data.old_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Kata sandi lama Anda salah!")

    # Timpa dengan password baru yang di-hash
    user.password_hash = get_password_hash(data.new_password)
    db.commit()
    return {"message": "Kata sandi berhasil diperbarui"}


# ==========================================
# API 3: UPLOAD FOTO PROFIL (AVATAR)
# ==========================================
@router.post("/users/{username}/avatar")
def upload_avatar(
    username: str, file: UploadFile = File(...), db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(status_code=404, detail="Akun tidak ditemukan")

    # Buat folder static/avatars jika belum ada
    upload_dir = "static/avatars"
    os.makedirs(upload_dir, exist_ok=True)

    # Simpan file dengan nama unik
    file_ext = file.filename.split(".")[-1]
    file_name = f"avatar_{username}.{file_ext}"
    file_path = os.path.join(upload_dir, file_name)

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Simpan path gambar ke database (menggunakan forward slash untuk URL web yang valid)
    user.avatar = f"/static/avatars/{file_name}"
    db.commit()

    return {"message": "Foto profil berhasil diperbarui", "avatar_url": user.avatar}
