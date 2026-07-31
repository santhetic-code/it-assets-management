from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

# 1. Kita paksa (hardcode) koneksi langsung ke MySQL Laragon di sini
# Ini akan mengabaikan fallback SQLite dan memastikan tabel masuk ke itam_db
SQLALCHEMY_DATABASE_URL = "mysql+pymysql://root@localhost:3306/itam_db"

# 2. Pembuatan Mesin Database (Engine)
engine = create_engine(SQLALCHEMY_DATABASE_URL)

# 3. Pembuatan Sesi Database
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)