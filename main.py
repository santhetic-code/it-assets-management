from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

# Import Database & Inisialisasi
from app.core.database import engine
from app.models import domain
from app.core.deps import DbSession
from app.services.auth_service import init_superadmin

# Import semua Router yang sudah kita buat
from app.routers import auth, vault, ips, assets, pages

# 1. Inisialisasi Tabel Database
domain.Base.metadata.create_all(bind=engine)

# 2. Inisialisasi FastAPI
app = FastAPI(title="ITAM Pro Enterprise", version="2.0.0")

# 3. Mount Folder Statis (CSS, JS, Avatar)
app.mount("/static", StaticFiles(directory="static"), name="static")

# 4. Daftarkan Semua Router
app.include_router(pages.router)     # Rute Halaman HTML
app.include_router(auth.router)      # API Login & User
app.include_router(vault.router)     # API Brankas Kredensial
app.include_router(ips.router)       # API Jaringan IP
app.include_router(assets.router)    # API Aset, Komponen, Pembelian, Maintenance

# 5. Event Startup (Otomatis jalan saat server menyala)
@app.on_event("startup")
def on_startup():
    # Membuat Session manual khusus untuk startup
    from app.core.database import SessionLocal
    db = SessionLocal()
    try:
        # Inisialisasi Super Admin dari file .env dengan aman
        init_superadmin(db)
    finally:
        db.close()