from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException, status

from app.models.domain import NetworkIP
from app.models.schemas.network_ip import NetworkIPCreate, NetworkIPUpdate

def get_all_ips(db: Session):
    return db.query(NetworkIP).all()

def create_ip(db: Session, ip_data: NetworkIPCreate):
    # Mengubah Pydantic schema menjadi dictionary untuk SQLAlchemy
    new_ip = NetworkIP(**ip_data.model_dump())
    try:
        db.add(new_ip)
        db.commit()
        db.refresh(new_ip)
        return new_ip
    except IntegrityError:
        db.rollback()
        # Solusi Bug #8: Menangkap error duplikat dari database
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Alamat IP {ip_data.ip_address} sudah terdaftar di sistem."
        )

def update_ip(db: Session, ip_id: int, ip_data: NetworkIPUpdate):
    db_ip = db.query(NetworkIP).filter(NetworkIP.id == ip_id).first()
    if not db_ip:
        raise HTTPException(status_code=404, detail="Data IP tidak ditemukan.")
    
    # Hanya mengupdate field yang benar-benar dikirimkan user (exclude_unset=True)
    update_data = ip_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_ip, key, value)
        
    try:
        db.commit()
        db.refresh(db_ip)
        return db_ip
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Alamat IP yang diubah bertabrakan dengan IP lain yang sudah ada."
        )

def delete_ip(db: Session, ip_id: int):
    db_ip = db.query(NetworkIP).filter(NetworkIP.id == ip_id).first()
    if not db_ip:
        raise HTTPException(status_code=404, detail="Data IP tidak ditemukan.")
    
    db.delete(db_ip)
    db.commit()
    return {"message": "Data IP berhasil dihapus."}
