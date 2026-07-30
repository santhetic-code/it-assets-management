from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException, status

from app.models.domain import User
from app.models.schemas.user import UserCreate, UserUpdate
from app.core.security import get_password_hash, verify_password
from app.core.config import settings

def init_superadmin(db: Session):
    """
    Dijalankan sekali saat aplikasi start.
    Membaca kredensial dari .env, menggantikan backdoor 'developer' lama.
    """
    first_user = db.query(User).first()
    if not first_user:
        hashed_pw = get_password_hash(settings.SUPERADMIN_PASSWORD)
        super_admin = User(
            username=settings.SUPERADMIN_USERNAME,
            password_hash=hashed_pw,
            role="Super Admin"
        )
        db.add(super_admin)
        db.commit()

def authenticate_user(db: Session, username: str, password: str):
    user = db.query(User).filter(User.username == username).first()
    if not user or not verify_password(password, user.password_hash):
        return None
    return user

def get_all_users(db: Session):
    return db.query(User).all()

def create_user(db: Session, user_data: UserCreate):
    hashed_pw = get_password_hash(user_data.password)
    db_data = user_data.model_dump()
    db_data["password_hash"] = hashed_pw
    del db_data["password"]

    new_user = User(**db_data)
    try:
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        return new_user
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username sudah digunakan oleh pengguna lain."
        )

def update_user(db: Session, user_id: int, user_data: UserUpdate):
    db_user = db.query(User).filter(User.id == user_id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="Pengguna tidak ditemukan.")
    
    update_data = user_data.model_dump(exclude_unset=True)
    
    # Jika password ikut diubah, hash ulang
    if "password" in update_data and update_data["password"]:
        update_data["password_hash"] = get_password_hash(update_data["password"])
        
    update_data.pop("password", None)
    
    for key, value in update_data.items():
        setattr(db_user, key, value)
        
    try:
        db.commit()
        db.refresh(db_user)
        return db_user
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Username bertabrakan dengan pengguna lain.")

def delete_user(db: Session, user_id: int, current_user_id: int):
    # Mencegah Super Admin menghapus dirinya sendiri
    if user_id == current_user_id:
        raise HTTPException(status_code=400, detail="Anda tidak dapat menghapus akun Anda sendiri.")
        
    db_user = db.query(User).filter(User.id == user_id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="Pengguna tidak ditemukan.")
    
    db.delete(db_user)
    db.commit()
    return {"message": "Pengguna berhasil dihapus."}
