from app.core.config import settings
from app.core.database import SessionLocal, engine
from app.core.security import get_password_hash
from app.models import domain


def seed_admin():
    # 1. Generate semua tabel ke database jika belum ada
    domain.Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        # Cek apakah user admin sesuai .env sudah ada
        existing_user = (
            db.query(domain.User)
            .filter(domain.User.username == settings.SUPERADMIN_USERNAME)
            .first()
        )
        if not existing_user:
            # Disesuaikan dengan kredensial dinamis dari app.core.config (.env)
            admin_user = domain.User(
                username=settings.SUPERADMIN_USERNAME,
                password_hash=get_password_hash(settings.SUPERADMIN_PASSWORD),
                role="Super Admin",
            )
            db.add(admin_user)
            db.commit()
            print(
                f"✅ Database berhasil dibuat dan User Admin '{settings.SUPERADMIN_USERNAME}' berhasil disuntikkan dari .env!"
            )
        else:
            print(f"ℹ️ User admin '{settings.SUPERADMIN_USERNAME}' sudah ada di database.")
    except Exception as e:
        db.rollback()
        print(f"❌ Terjadi kesalahan saat seeding: {e}")
        raise e
    finally:
        db.close()


if __name__ == "__main__":
    seed_admin()
