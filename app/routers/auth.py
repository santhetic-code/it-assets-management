from datetime import datetime, timedelta
import os
import shutil
from typing import List, Optional
from fastapi import APIRouter, Depends, File, HTTPException, Request, Response, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import (
    CurrentUser,
    DbSession,
    get_audit_logger,
    get_current_super_admin,
    get_current_user,
    require_super_admin,
)
from app.core.security import (
    SECURE_COOKIES,
    create_access_token,
    get_password_hash,
    verify_jwt_token,
    verify_password,
)
from app.models.domain import User
from app.models.schemas.user import UserCreate, UserResponse, UserUpdate
from app.services import auth_service

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


def set_auth_cookies(response: Response, user: User):
    """
    Helper untuk men-generate JWT Token baru dan memperbarui cookie.
    Payload token disterilisasi hanya berisi klaim sub (Subject) unik pengguna.
    """
    access_token = create_access_token(
        data={"sub": user.username}
    )
    response.set_cookie(
        key="access_token",
        value=f"Bearer {access_token}",
        httponly=True,
        secure=SECURE_COOKIES,
        samesite="lax",
        max_age=7200,
        expires=7200,
    )
    response.set_cookie(
        key="itam_session",
        value=access_token,
        httponly=True,
        secure=SECURE_COOKIES,
        samesite="lax",
        max_age=7200,
        expires=7200,
    )
    return access_token


class LogoutRequest(BaseModel):
    username: str


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

    # Nyalakan radar online dan rekam waktu terakhir login (WIB)
    user.is_online = True
    user.last_login = datetime.utcnow() + timedelta(hours=7)
    db.commit()

    # 4. Buat Tiket JWT & Tanamkan ke Cookie Browser
    set_auth_cookies(response, user)
    nama_tampil = user.full_name if user.full_name else user.username
    role_tampil = user.role if user.role else "Staff IT"

    return {"message": "Berhasil Login", "name": nama_tampil, "role": role_tampil}


@router.post("/logout")
def logout(
    response: Response,
    request: Request,
    request_data: Optional[LogoutRequest] = None,
    db: Session = Depends(get_db),
):
    # Matikan radar online di database
    target_username = request_data.username if request_data and request_data.username else None
    if not target_username:
        token = request.cookies.get("access_token") or request.cookies.get("itam_session")
        if token:
            try:
                payload = verify_jwt_token(token)
                sub = payload.get("sub")
                if str(sub).isdigit():
                    u = db.query(User).filter(User.id == int(sub)).first()
                    if u:
                        target_username = u.username
                else:
                    target_username = payload.get("username") or sub
            except Exception:
                pass

    if target_username:
        user = db.query(User).filter(User.username == target_username).first()
        if user:
            user.is_online = False
            db.commit()

    # Hancurkan tiket sesi
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
# API 1: TAMBAH PENGGUNA BARU (TERKUNCI)
# ==========================================
@router.post("/users", dependencies=[Depends(get_current_super_admin)])
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


# ==========================================
# API: UPDATE PROFIL UTAMA (Oleh User Sendiri)
# ==========================================
@router.put("/users/profile")
def update_profile(
    data: UserUpdate,
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    current_user.full_name = data.full_name
    current_user.email = data.email
    current_user.phone = data.phone
    current_user.department = data.department

    db.commit()

    # Regenerasi JWT Token baru agar profil tersinkronisasi di seluruh halaman
    set_auth_cookies(response, current_user)

    return {"message": "Profil berhasil diperbarui", "name": current_user.full_name}


@router.put(
    "/users/{user_id}",
    response_model=UserResponse,
    dependencies=[Depends(require_super_admin), Depends(get_audit_logger)],
)
def update_user(user_id: int, user_data: UserUpdate, db: DbSession):
    return auth_service.update_user(db, user_id, user_data)


# ==========================================
# API: HAPUS PENGGUNA (TERKUNCI)
# ==========================================
@router.delete("/users/{user_id}", dependencies=[Depends(get_current_super_admin)])
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
    username: str,
    response: Response,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
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

    # Regenerasi JWT Token baru agar avatar tersinkronisasi di seluruh halaman
    set_auth_cookies(response, user)

    return {"message": "Foto profil berhasil diperbarui", "avatar_url": user.avatar}
