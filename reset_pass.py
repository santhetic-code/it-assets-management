from app.core.database import SessionLocal
from app.core.security import get_password_hash
from app.models.domain import User

db = SessionLocal()

# Cari user dengan username 'developer'
user = db.query(User).filter(User.username == "developer").first()

if user:
    # Update password menjadi 'admin123' dengan enkripsi baru
    user.password_hash = get_password_hash("admin123")
    db.commit()
    print("Berhasil! Password akun 'developer' sekarang adalah: admin123")
else:
    print("Gagal: User 'developer' tidak ditemukan di database.")

db.close()
