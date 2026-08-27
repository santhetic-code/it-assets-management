from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import settings

# 1. Koneksi Dinamis menggunakan parameter DATABASE_URL dari .env
engine = create_engine(settings.DATABASE_URL)

# 2. Pembuatan Sesi Database
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 3. Fondasi Base untuk model tabel
Base = declarative_base()


# 4. Generator Sesi Database untuk FastAPI
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()