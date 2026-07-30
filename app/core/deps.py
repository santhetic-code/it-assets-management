from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import verify_jwt_token

# Catatan: Kita akan mengaktifkan import ini di langkah selanjutnya
# setelah kita memindahkan file models.py lama.
# from app.models.domain import User

def get_current_user(request: Request, db: Session = Depends(get_db)):
    """
    Penjaga Lapis 1: Mengecek apakah pengguna sudah login dan memiliki token valid.
    Akan dipasang pada SEMUA endpoint yang butuh autentikasi.
    """
    token = request.cookies.get("itam_session")
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Akses Ditolak: Silakan login terlebih dahulu."
        )
    
    # Verifikasi token dan ambil isinya (payload)
    payload = verify_jwt_token(token)
    user_id = payload.get("sub")
    
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Token tidak valid."
        )
        
    # --- BLOK INI AKAN KITA AKTIFKAN SETELAH MEMBUAT app/models/domain.py ---
    # user = db.query(User).filter(User.id == user_id).first()
    # if not user:
    #     raise HTTPException(status_code=401, detail="Akun pengguna tidak ditemukan di sistem.")
    # return user
    # ------------------------------------------------------------------------
    
    # SEMENTARA (Mencegah error IDE sebelum model database kita pindahkan):
    class DummyUser:
        id = user_id
        role = payload.get("role", "Auditor") # Fallback ke role terendah untuk keamanan
    return DummyUser()

def require_staff_or_admin(current_user = Depends(get_current_user)):
    """
    Penjaga Lapis 2: Memblokir pengguna dengan role 'Auditor/Viewer'.
    Akan dipasang pada endpoint POST/PUT/DELETE (Ubah Data).
    """
    if current_user.role not in ["Super Admin", "Staff IT"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Akses Ditolak: Hak akses Anda hanya untuk melihat data (Read-Only)."
        )
    return current_user

def require_super_admin(current_user = Depends(get_current_user)):
    """
    Penjaga Lapis 3: Hanya Super Admin yang boleh lewat.
    Untuk hapus akun, ubah role, dsb.
    """
    if current_user.role != "Super Admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Akses Ditolak: Otorisasi khusus Super Admin."
        )
    return current_user

def get_audit_logger(request: Request, current_user = Depends(get_current_user)):
    """
    (Opsional/Draft) Pengganti audit_logger lama untuk mencatat IP dan User ID.
    Kita akan menyempurnakannya saat masuk ke modul Services.
    """
    client_ip = request.client.host if request.client else "Unknown"
    return {"user_id": current_user.id, "ip": client_ip}
