from typing import Annotated

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session
import jwt

from app.core.database import get_db
from app.models.domain import User
from app.core.security import SECRET_KEY, ALGORITHM


# 1. Mengekstrak JWT dari Cookie Browser
def get_token_from_cookie(request: Request):
    token = request.cookies.get("access_token") or request.cookies.get("itam_session")
    if not token:
        raise HTTPException(status_code=401, detail="Sesi telah habis, silakan login kembali.")
    return token.replace("Bearer ", "")


# 2. Satpam Pengecek Identitas User
def get_current_user(token: str = Depends(get_token_from_cookie), db: Session = Depends(get_db)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=401, detail="Kredensial tidak valid.")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Tiket sesi tidak valid atau kedaluwarsa.")
        
    if str(username).isdigit():
        user = db.query(User).filter(User.id == int(username)).first()
    else:
        user = db.query(User).filter(User.username == username).first()

    if user is None:
        raise HTTPException(status_code=404, detail="Akun tidak ditemukan.")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Akun dinonaktifkan.")
        
    return user


# 3. Satpam Khusus Super Admin (Gembok RBAC)
def require_super_admin(current_user: User = Depends(get_current_user)):
    if current_user.role != "Super Admin":
        raise HTTPException(
            status_code=403,
            detail="Akses Ditolak: Tindakan destruktif ini memerlukan izin Super Admin.",
        )
    return current_user

get_current_super_admin = require_super_admin


# =========================================================================
# HELPER DEPENDENCIES & TYPE ALIASES (UNTUK KOMPATIBILITAS SELURUH ROUTER)
# =========================================================================
DbSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]


def require_staff_or_admin(current_user: User = Depends(get_current_user)):
    # Sesuaikan persis dengan value yang ada di database Anda ("IT Support" atau "Staff IT")
    allowed_roles = ["Super Admin", "Staff", "IT Support", "Staff IT"]
    if current_user.role not in allowed_roles:
        raise HTTPException(
            status_code=403,
            detail="Akses Ditolak: Hak akses Anda hanya untuk Read-Only.",
        )
    return current_user


def get_audit_logger(request: Request, current_user: CurrentUser):
    client_ip = request.client.host if request.client else "Unknown"
    return {"user_id": current_user.id, "ip": client_ip}
