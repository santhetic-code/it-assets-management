from app.core.database import SessionLocal
from app.core.security import get_password_hash
from app.models.domain import User

db = SessionLocal()

# Mencari akun Anda
user = db.query(User).filter(User.username == "developer").first()

if user:
    # Mengunci password Anda dengan mesin enkripsi baru
    user.password_hash = get_password_hash("XML01022007")
    db.commit()
    print("Berhasil! Sistem sekarang mengenali password: XML01022007")
else:
    print("Gagal: User tidak ditemukan.")

db.close()
