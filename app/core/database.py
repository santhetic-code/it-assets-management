from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.core.config import settings

# 1. Koneksi langsung ke MySQL Laragon
SQLALCHEMY_DATABASE_URL = "mysql+pymysql://root@localhost:3306/itam_db"

# 2. Pembuatan Mesin Database (Engine)
engine = create_engine(SQLALCHEMY_DATABASE_URL)

# 3. Pembuatan Sesi Database
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 4. Fondasi Base untuk model tabel
Base = declarative_base()

# 5. FUNGSI YANG HILANG: Generator Sesi Database untuk FastAPI
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()