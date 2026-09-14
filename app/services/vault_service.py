from sqlalchemy.orm import Session
from app.models.domain import VaultCredential
from app.models.schemas.credential import VaultCreate, VaultUpdate

def get_vaults(db: Session):
    return db.query(VaultCredential).all()

def create_vault(db: Session, vault: VaultCreate):
    # model_dump() mengubah skema Pydantic menjadi format Dictionary (JSON) yang siap masuk ke DB
    db_vault = VaultCredential(**vault.model_dump())
    db.add(db_vault)
    db.commit()
    db.refresh(db_vault)
    return db_vault

def update_vault(db: Session, vault_id: int, vault: VaultUpdate):
    db_vault = db.query(VaultCredential).filter(VaultCredential.id == vault_id).first()
    if db_vault:
        for key, value in vault.model_dump().items():
            setattr(db_vault, key, value)
        db.commit()
        db.refresh(db_vault)
    return db_vault

def delete_vault(db: Session, vault_id: int):
    db_vault = db.query(VaultCredential).filter(VaultCredential.id == vault_id).first()
    if db_vault:
        db.delete(db_vault)
        db.commit()
        return True
    return False
