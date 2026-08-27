from app.core.database import engine, SessionLocal
from app.models import domain
from app.core.security import get_password_hash

# 1. Generate semua tabel ke database
domain.Base.metadata.create_all(bind=engine)

def seed_admin():
    db = SessionLocal()
    try:
        # Cek apakah user admin sudah ada
        existing_user = db.query(domain.User).filter(domain.User.username == "admin").first()
        if not existing_user:
            # Disesuaikan dengan kolom pada domain.User:
            # - role: "Super Admin" (sesuai app/core/deps.py)
            # - kolom 'is_active' dihilangkan karena tidak ada di domain.py
            admin_user = domain.User(
                username="admin",
                password_hash=get_password_hash("admin123"),
                role="Super Admin"
            )
            db.add(admin_user)
            db.commit()
            print("Database berhasil dibuat dan User Admin berhasil disuntikkan!")
        else:
            print("User admin sudah ada.")
    except Exception as e:
        db.rollback()
        print(f"Terjadi kesalahan saat seeding: {e}")
        raise e
    finally:
        db.close()

if __name__ == "__main__":
    seed_admin()
