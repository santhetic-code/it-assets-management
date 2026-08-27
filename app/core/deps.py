from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import verify_jwt_token
from app.models.domain import User

# Type Alias untuk Session Database
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

    # Verifikasi token dan ambil isinya
    payload = verify_jwt_token(token)
    user_id = payload.get("sub")

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Token tidak valid."
        )

    # Mengambil data asli dari database (mendukung user_id numerik maupun username)
    if str(user_id).isdigit():
        user = db.query(User).filter(User.id == int(user_id)).first()
    else:
        user = db.query(User).filter(User.username == user_id).first()

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
