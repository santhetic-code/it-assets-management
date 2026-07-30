from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from cryptography.fernet import Fernet, InvalidToken

from app.models.domain import Credential, SystemLogs
from app.models.schemas.credential import CredentialCreate, CredentialUpdate
from app.core.config import settings

# Inisialisasi Kunci Brankas (Fernet) menggunakan VAULT_KEY dari .env
f = Fernet(settings.VAULT_KEY.encode())

def get_all_credentials(db: Session):
    return db.query(Credential).all()

def create_credential(db: Session, cred_data: CredentialCreate):
    # Enkripsi password menggunakan Fernet sebelum masuk ke database
    encrypted_pwd = f.encrypt(cred_data.password.encode()).decode()
    
    db_data = cred_data.model_dump()
    db_data["password_hash"] = encrypted_pwd
    del db_data["password"] # Hapus key password mentah karena nama kolomnya password_hash
    
    new_cred = Credential(**db_data)
    db.add(new_cred)
    db.commit()
    db.refresh(new_cred)
    return new_cred

def update_credential(db: Session, cred_id: int, cred_data: CredentialUpdate):
    db_cred = db.query(Credential).filter(Credential.id == cred_id).first()
    if not db_cred:
        raise HTTPException(status_code=404, detail="Kredensial tidak ditemukan.")
    
    update_data = cred_data.model_dump(exclude_unset=True)
    
    # SOLUSI BUG #4: Hanya enkripsi dan timpa password JIKA field diisi oleh pengguna
    if "password" in update_data and update_data["password"]:
        encrypted_pwd = f.encrypt(update_data["password"].encode()).decode()
        update_data["password_hash"] = encrypted_pwd
        
    # Hapus field password mentah agar tidak terjadi bentrok dengan model SQLAlchemy
    update_data.pop("password", None)
    
    for key, value in update_data.items():
        setattr(db_cred, key, value)
        
    db.commit()
    db.refresh(db_cred)
    return db_cred

def delete_credential(db: Session, cred_id: int):
    db_cred = db.query(Credential).filter(Credential.id == cred_id).first()
    if not db_cred:
        raise HTTPException(status_code=404, detail="Kredensial tidak ditemukan.")
    
    db.delete(db_cred)
    db.commit()
    return {"message": "Kredensial berhasil dihapus."}

def reveal_password(db: Session, cred_id: int, user_id: int, client_ip: str):
    db_cred = db.query(Credential).filter(Credential.id == cred_id).first()
    if not db_cred:
        raise HTTPException(status_code=404, detail="Kredensial tidak ditemukan.")
    
    try:
        # Dekripsi password menggunakan VAULT_KEY
        decrypted_pwd = f.decrypt(db_cred.password_hash.encode()).decode()
    except InvalidToken:
        raise HTTPException(status_code=500, detail="Gagal mendekripsi password. VAULT_KEY tidak valid.")
        
    # SOLUSI KERENTANAN #6: Mencatat aksi "Reveal" ke tabel Audit Trail
    log_entry = SystemLogs(
        user_id=user_id,
        action="Melihat/Menyalin Password",
        entity="Credential",
        entity_id=db_cred.id,
        ip_address=client_ip
    )
    db.add(log_entry)
    db.commit()
    
    return {"password": decrypted_pwd}
