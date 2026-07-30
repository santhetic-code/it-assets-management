from typing import Annotated, Any

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import verify_jwt_token

from app.models.domain import User

# -------------------------------------------------------------------
# TYPE ALIASES (Solusi elegan untuk mengatasi Ruff B008)
# Memindahkan Depends() ke dalam tipe data agar linter tidak protes.
# -------------------------------------------------------------------
DbSession = Annotated[Session, Depends(get_db)]


def get_current_user(request: Request, db: DbSession):
    """
    Penjaga Lapis 1: Mengecek apakah pengguna sudah login dan memiliki token valid.
    """
    token = request.cookies.get("itam_session")
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Akses Ditolak: Silakan login terlebih dahulu.",
        )

    # Verifikasi token dan ambil isinya (payload)
    payload = verify_jwt_token(token)
    user_id = payload.get("sub")

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Token tidak valid."
        )

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Akun pengguna tidak ditemukan di sistem.",
        )
    return user


# Type Alias untuk Current User
CurrentUser = Annotated[User, Depends(get_current_user)]


def require_staff_or_admin(current_user: CurrentUser):
    """
    Penjaga Lapis 2: Memblokir pengguna dengan role 'Auditor/Viewer'.
    Akan dipasang pada endpoint POST/PUT/DELETE (Ubah Data).
    """
    if current_user.role not in ["Super Admin", "Staff IT"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Akses Ditolak: Hak akses Anda hanya untuk melihat data (Read-Only).",
        )
    return current_user


def require_super_admin(current_user: CurrentUser):
    """
    Penjaga Lapis 3: Hanya Super Admin yang boleh lewat.
    """
    if current_user.role != "Super Admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Akses Ditolak: Otorisasi khusus Super Admin.",
        )
    return current_user


def get_audit_logger(request: Request, current_user: CurrentUser):
    """
    Mencatat IP dan User ID.
    """
    client_ip = request.client.host if request.client else "Unknown"
    return {"user_id": current_user.id, "ip": client_ip}
