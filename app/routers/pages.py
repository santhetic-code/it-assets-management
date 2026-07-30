from fastapi import APIRouter, Request, Depends
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse

from app.core.deps import DbSession
from app.models.domain import Asset, Component, NetworkIP, MaintenanceLog

router = APIRouter(tags=["Web Pages"])

# Mengarahkan Jinja2 ke folder views
templates = Jinja2Templates(directory="views")

@router.get("/", response_class=HTMLResponse)
async def read_dashboard(request: Request, db: DbSession):
    """
    Render halaman Dashboard dan hitung statistik real-time (Solusi Bug #1).
    """
    total_assets = db.query(Asset).count()
    total_components = db.query(Component).count()
    active_ips = db.query(NetworkIP).filter(NetworkIP.status == "Aktif").count()
    pending_maintenance = db.query(MaintenanceLog).filter(MaintenanceLog.status != "Aman").count()

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "total_assets": total_assets,
            "total_components": total_components,
            "active_ips": active_ips,
            "pending_maintenance": pending_maintenance
        }
    )

@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={}
    )

# (Tambahkan rute halaman lainnya seperti /assets, /vault, dll yang merender HTML masing-masing)
# Contoh:
@router.get("/vault", response_class=HTMLResponse)
async def vault_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="credentials.html",
        context={}
    )
