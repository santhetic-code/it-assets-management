from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.core.database import get_db
from app.core.deps import get_current_user, require_super_admin
from app.models.domain import Vault, VaultUserAccess, User
from app.models.schemas.vault import VaultCreate, VaultResponse, DecryptResponse, VaultAccessToggle
# Import mesin enkripsi kita!
from app.core.security import encrypt_payload, decrypt_payload, verify_csrf_token

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
@router.post("/", response_model=VaultResponse, dependencies=[Depends(require_super_admin), Depends(verify_csrf_token)])
def create_vault(vault_in: VaultCreate, db: Session = Depends(get_db)):
    # 1. Enkripsi seluruh JSON menjadi satu string acak Fernet
    encrypted_str = encrypt_payload(vault_in.secrets)
    
    # 2. Simpan ke database
    new_vault = Vault(
        name=vault_in.name,
        category=vault_in.category,
        url=vault_in.url,
        description=vault_in.description,
        encrypted_payload=encrypted_str  # Simpan payload di sini
    )
    db.add(new_vault)
    db.commit()
    db.refresh(new_vault)
    
    return new_vault

# ==========================================
# 3. ON-DEMAND DECRYPTION (SAAT TOMBOL REVEAL DIKLIK)
# ==========================================
@router.get("/{vault_id}/decrypt", response_model=DecryptResponse)
def decrypt_vault(vault_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    vault = db.query(Vault).filter(Vault.id == vault_id).first()
    if not vault:
        raise HTTPException(status_code=404, detail="Kredensial tidak ditemukan")

    # Logika Cek Akses
    if current_user.role != "Super Admin":
        access = db.query(VaultUserAccess).filter(
            VaultUserAccess.vault_id == vault_id,
            VaultUserAccess.user_id == current_user.id
        ).first()
        if not access:
            raise HTTPException(status_code=403, detail="Anda tidak memiliki izin mengakses kredensial ini")

    # Dekripsi payload menjadi dictionary kembali
    try:
        decrypted_dict = decrypt_payload(vault.encrypted_payload)
        return {"secrets": decrypted_dict}
    except Exception as e:
        raise HTTPException(status_code=500, detail="Gagal mendekripsi data. Kunci mungkin tidak cocok.")

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
@router.post("/{vault_id}/access", dependencies=[Depends(require_super_admin), Depends(verify_csrf_token)])
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


# ==========================================
# 6. UPDATE KREDENSIAL (RE-ENCRYPT)
# ==========================================
@router.put("/{vault_id}", response_model=VaultResponse, dependencies=[Depends(require_super_admin), Depends(verify_csrf_token)])
def update_vault(vault_id: int, vault_in: VaultCreate, db: Session = Depends(get_db)):
    vault = db.query(Vault).filter(Vault.id == vault_id).first()
    if not vault:
        raise HTTPException(status_code=404, detail="Kredensial tidak ditemukan")
    
    # 1. Enkripsi ulang JSON secrets dengan data yang baru diedit
    encrypted_str = encrypt_payload(vault_in.secrets)
    
    # 2. Update data ke MariaDB
    vault.name = vault_in.name
    vault.category = vault_in.category
    vault.url = vault_in.url
    vault.description = vault_in.description
    vault.encrypted_payload = encrypted_str
    
    db.commit()
    db.refresh(vault)
    return vault


# ==========================================
# 7. HAPUS KREDENSIAL PERMANEN
# ==========================================
@router.delete("/{vault_id}", dependencies=[Depends(require_super_admin), Depends(verify_csrf_token)])
def delete_vault(vault_id: int, db: Session = Depends(get_db)):
    vault = db.query(Vault).filter(Vault.id == vault_id).first()
    if not vault:
        raise HTTPException(status_code=404, detail="Kredensial tidak ditemukan")
    
    db.delete(vault)
    db.commit()
    return {"message": "Kredensial berhasil dihancurkan secara permanen"}

