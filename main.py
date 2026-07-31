from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse, JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.database import engine, SessionLocal
from app.models import domain

# Import seluruh router dari arsitektur MVC kita
from app.routers import auth, vault, ips, assets, pages

# 1. Bangun fondasi database secara otomatis
domain.Base.metadata.create_all(bind=engine)

app = FastAPI(title="ITAM Pro Enterprise")

# 2. Mount folder static (CSS, JS, Gambar)
app.mount("/static", StaticFiles(directory="static"), name="static")

# 3. Pengatur Lalu Lintas Cerdas (Pencegah Infinite Loop)
# Jika ada error 401 (Belum Login) di halaman Web, lempar ke /login.
# Jika error 401 di endpoint /api/, biarkan tetap merespons format JSON.
@app.exception_handler(StarletteHTTPException)
async def custom_auth_exception_handler(request: Request, exc: StarletteHTTPException):
    if exc.status_code == 401:
        if not request.url.path.startswith("/api/"):
            return RedirectResponse(url="/login")
    return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)

# 4. Daftarkan semua endpoint
app.include_router(auth.router)
app.include_router(vault.router)
app.include_router(ips.router)
app.include_router(assets.router)
app.include_router(pages.router)

# 5. Inisialisasi Data Pertama Kali Saat Server Menyala
@app.on_event("startup")
def startup_event():
    from app.services.auth_service import init_superadmin
    db = SessionLocal()
    try:
        # Menembakkan pembuatan akun dari .env ke dalam database
        init_superadmin(db)
    finally:
        db.close()