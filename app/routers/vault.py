from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.core.database import get_db
from app.models.domain import Vault, VaultUserAccess, User
from app.models.schemas.vault import VaultCreate, VaultResponse, DecryptResponse, VaultAccessToggle
from app.core.deps import get_current_user, require_super_admin
from app.core.security import encrypt_vault_data, decrypt_vault_data

router = APIRouter(prefix="/api/vaults", tags=["Credential Vault"])

# ==========================================
# 1. TAMPILKAN KREDENSIAL (TANPA SANDI & BERDASARKAN ACL)
# ==========================================
@router.get("/", response_model=List[VaultResponse])
def get_vaults(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if current_user.role == "Super Admin":
        # God Mode: Lihat semua nama aset
        vaults = db.query(Vault).all()
    else:
        # Staff Mode: Hanya lihat aset yang diizinkan di tabel relasi (VaultUserAccess)
        access_records = db.query(VaultUserAccess.vault_id).filter(VaultUserAccess.user_id == current_user.id).all()
        allowed_ids = [record[0] for record in access_records]
        
        vaults = db.query(Vault).filter(Vault.id.in_(allowed_ids)).all()
        
    return vaults

# ==========================================
# 2. TAMBAH KREDENSIAL BARU (LANGSUNG ENKRIPSI)
# ==========================================
@router.post("/", dependencies=[Depends(require_super_admin)])
def create_vault(data: VaultCreate, db: Session = Depends(get_db)):
    new_vault = Vault(
        name=data.name,
        category=data.category,
        url=data.url,
        username=data.username,
        encrypted_password=encrypt_vault_data(data.password), # 🔒 PROSES ENKRIPSI AES
        description=data.description
    )
    db.add(new_vault)
    db.commit()
    return {"message": "Kredensial berhasil diamankan ke dalam Vault."}

# ==========================================
# 3. ON-DEMAND DECRYPTION (SAAT TOMBOL REVEAL DIKLIK)
# ==========================================
@router.get("/{vault_id}/decrypt", response_model=DecryptResponse)
def decrypt_password(vault_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    vault = db.query(Vault).filter(Vault.id == vault_id).first()
    if not vault:
        raise HTTPException(status_code=404, detail="Kredensial tidak ditemukan.")
    
    # Validasi Izin Akses (Zero-Trust)
    if current_user.role != "Super Admin":
        access = db.query(VaultUserAccess).filter(
            VaultUserAccess.vault_id == vault_id,
            VaultUserAccess.user_id == current_user.id
        ).first()
        
        if not access:
            raise HTTPException(status_code=403, detail="Bypass Terdeteksi: Anda tidak memiliki izin untuk mendekripsi sandi ini.")
            
        # TODO: Di sini nanti kita tambahkan pengecekan `expires_at` untuk akses sementara
    
    # 🔓 Buka Gembok AES (Dekripsi)
    raw_password = decrypt_vault_data(vault.encrypted_password)
    
    # TODO: Logika Audit Trail (Mencatat siapa yang melihat sandi ini) akan ditambahkan di sini
    
    return {"password": raw_password}

# ==========================================
# 4. AMBIL DAFTAR STAF & STATUS AKSES (KHUSUS SUPER ADMIN)
# ==========================================
@router.get("/{vault_id}/access", dependencies=[Depends(require_super_admin)])
def get_vault_access(vault_id: int, db: Session = Depends(get_db)):
    # Pastikan kredensial ada
    vault = db.query(Vault).filter(Vault.id == vault_id).first()
    if not vault:
        raise HTTPException(status_code=404, detail="Kredensial tidak ditemukan.")

    # Ambil semua user KECUALI Super Admin (karena Super Admin otomatis punya akses)
    users = db.query(User).filter(User.role != "Super Admin").all()
    
    # Cek siapa saja yang ID-nya ada di tabel VaultUserAccess
    accesses = db.query(VaultUserAccess.user_id).filter(VaultUserAccess.vault_id == vault_id).all()
    access_user_ids = [a[0] for a in accesses]

    result = []
    for u in users:
        result.append({
            "user_id": u.id,
            "username": u.username,
            "full_name": u.full_name or u.username,
            "department": u.department or "-",
            "has_access": u.id in access_user_ids
        })
    
    return result

# ==========================================
# 5. EKSEKUSI TOMBOL TOGGLE ON/OFF HAK AKSES
# ==========================================
@router.post("/{vault_id}/access", dependencies=[Depends(require_super_admin)])
def toggle_vault_access(vault_id: int, data: VaultAccessToggle, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    # Cari apakah staf tersebut sudah punya akses sebelumnya
    existing_access = db.query(VaultUserAccess).filter(
        VaultUserAccess.vault_id == vault_id,
        VaultUserAccess.user_id == data.user_id
    ).first()

    if data.has_access and not existing_access:
        # Jika tombol di-ON-kan dan belum punya akses -> BERIKAN AKSES
        new_access = VaultUserAccess(vault_id=vault_id, user_id=data.user_id, granted_by=current_user.id)
        db.add(new_access)
    elif not data.has_access and existing_access:
        # Jika tombol di-OFF-kan dan sebelumnya punya akses -> CABUT AKSES
        db.delete(existing_access)
    
    db.commit()
    return {"message": "Hak akses berhasil diperbarui."}

