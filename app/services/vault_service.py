from datetime import datetime
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from app.core.security import decrypt_vault_payload, encrypt_vault_payload
from app.models.domain import Vault, VaultUserAccess
from app.models.schemas.vault import VaultCreate


def get_all_vaults(db: Session) -> List[Vault]:
    """Mengambil semua entri Vault dari database."""
    return db.query(Vault).all()


def get_vault_by_id(db: Session, vault_id: int) -> Optional[Vault]:
    """Mengambil satu entri Vault berdasarkan ID."""
    return db.query(Vault).filter(Vault.id == vault_id).first()


def create_vault_entry(
    db: Session,
    name: str,
    category: str,
    payload_dict: dict,
    url: Optional[str] = None,
    description: Optional[str] = None,
) -> Vault:
    """
    Menerima payload_dict (dict murni), dienkripsi di memori, 
    dan HANYA ciphertext yang dikirim ke database MySQL.
    """
    # ENKRIPSI TERJADI DI SINI
    secure_ciphertext = encrypt_vault_payload(payload_dict)

    db_vault = Vault(
        name=name,
        category=category,
        url=url,
        encrypted_payload=secure_ciphertext,
        description=description,
        created_at=datetime.utcnow(),
    )
    db.add(db_vault)
    db.commit()
    db.refresh(db_vault)
    return db_vault


def get_vault_entry_decrypted(db: Session, vault_id: int) -> Optional[dict]:
    """
    Mengambil ciphertext dari DB dan mendekripsinya kembali ke dictionary.
    Hanya dipanggil jika User memiliki otoritas (dicek di router).
    """
    db_vault = db.query(Vault).filter(Vault.id == vault_id).first()
    if not db_vault:
        return None
    
    # DEKRIPSI TERJADI DI SINI
    decrypted_payload = decrypt_vault_payload(db_vault.encrypted_payload)
    
    return {
        "id": db_vault.id,
        "name": db_vault.name,
        "category": db_vault.category,
        "url": db_vault.url,
        "description": db_vault.description,
        "decrypted_payload": decrypted_payload,  # Data asli siap disajikan ke Frontend
    }


def update_vault_entry(
    db: Session,
    vault_id: int,
    name: str,
    category: str,
    payload_dict: dict,
    url: Optional[str] = None,
    description: Optional[str] = None,
) -> Optional[Vault]:
    """Memperbarui metadata dan mengenkripsi ulang payload rahasia baru."""
    db_vault = get_vault_by_id(db, vault_id)
    if not db_vault:
        return None

    db_vault.name = name
    db_vault.category = category
    db_vault.url = url
    db_vault.description = description
    db_vault.encrypted_payload = encrypt_vault_payload(payload_dict)

    db.commit()
    db.refresh(db_vault)
    return db_vault


def delete_vault_entry(db: Session, vault_id: int) -> bool:
    """Menghapus entri Vault secara permanen."""
    db_vault = get_vault_by_id(db, vault_id)
    if not db_vault:
        return False
    db.delete(db_vault)
    db.commit()
    return True


# Alias fungsi untuk kompatibilitas
get_vaults = get_all_vaults
