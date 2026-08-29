from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.database import SessionLocal, engine
from app.core.deps import get_current_user
from app.models import domain

# Import seluruh router dari arsitektur MVC kita
from app.routers import assets, auth, ips, pages, vault

app = FastAPI(title="ITAM Pro Enterprise")

# 1. Mount folder static (CSS, JS, Gambar)
app.mount("/static", StaticFiles(directory="static"), name="static")


# 2. Pengatur Lalu Lintas Cerdas (Pencegah Infinite Loop)
# Jika ada error 401 (Belum Login) di halaman Web, lempar ke /login.
# Jika error 401 di endpoint /api/, biarkan tetap merespons format JSON.
@app.exception_handler(StarletteHTTPException)
async def custom_auth_exception_handler(request: Request, exc: StarletteHTTPException):
    if exc.status_code == 401:
        if not request.url.path.startswith("/api/"):
            return RedirectResponse(url="/login")
    return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)


# 3. Daftarkan semua endpoint
# Router Pages & Auth dibiarkan bebas karena memiliki aturannya sendiri di dalam file
app.include_router(auth.router)
app.include_router(pages.router)

# SEGEL KEAMANAN: Semua API Module sekarang WAJIB LOGIN!
app.include_router(vault.router, dependencies=[Depends(get_current_user)])
app.include_router(ips.router, dependencies=[Depends(get_current_user)])
app.include_router(assets.router, dependencies=[Depends(get_current_user)])


# 4. Inisialisasi Database & Akun Pertama Kali Saat Server Menyala (Guarded Startup)
@app.on_event("startup")
def startup_event():
    try:
        # Bangun fondasi tabel database secara otomatis jika belum ada
        domain.Base.metadata.create_all(bind=engine)
        print("[OK] Fondasi tabel database berhasil diverifikasi/dibuat.")
    except Exception as e:
        print(f"[WARN] Peringatan: Gagal menghubungkan atau menginisialisasi tabel database saat startup: {e}")
        return

    from app.services.auth_service import init_superadmin

    db = SessionLocal()
    try:
        # Menembakkan pembuatan akun dari .env ke dalam database
        init_superadmin(db)
        print("[OK] Inisialisasi akun Super Admin selesai.")
    except Exception as e:
        print(f"[WARN] Peringatan: Gagal menginisialisasi akun Super Admin: {e}")
    finally:
        db.close()