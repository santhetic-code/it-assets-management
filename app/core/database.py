from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import settings

# Membuat engine SQLAlchemy menggunakan DATABASE_URL dari file .env (via settings)
engine = create_engine(settings.DATABASE_URL)

# Membuat class SessionLocal untuk instansiasi sesi database pada setiap request
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class yang akan diwarisi oleh semua model ORM kita nanti
Base = declarative_base()


def get_db():
    """
    Dependency generator untuk mengelola siklus hidup sesi database.
    Akan membuka sesi saat request masuk, dan menutupnya secara otomatis
    (atau melakukan rollback jika error) setelah request selesai.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
